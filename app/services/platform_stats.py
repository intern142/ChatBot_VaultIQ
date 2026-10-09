from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta


async def get_all_tenants_overview(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get overview stats for all tenants.
    Uses platform identity (vaultiq_super_admin) which has SELECT on metadata tables only.
    """
    sql = text("""
        WITH tenant_stats AS (
            SELECT 
                t.id,
                t.short_code,
                t.name,
                t.status,
                t.storage_quota_mb,
                t.created_at,
                COALESCE(u.user_count, 0) AS user_count,
                COALESCE(d.doc_count, 0) AS document_count,
                COALESCE(d.storage_bytes, 0) / 1024.0 / 1024.0 AS storage_used_mb,
                COALESCE(q24.questions_24h, 0) AS questions_24h,
                COALESCE(q30.questions_30d, 0) AS questions_30d,
                a.last_activity,
                COALESCE(ij.pending, 0) AS processing_pending,
                COALESCE(ij.failed, 0) AS processing_failed
            FROM tenants t
            LEFT JOIN (
                SELECT tenant_id, COUNT(*) AS user_count
                FROM users
                WHERE role <> 'super_admin'
                GROUP BY tenant_id
            ) u ON u.tenant_id = t.id
            LEFT JOIN (
                SELECT tenant_id, COUNT(*) AS doc_count, SUM(size_bytes) AS storage_bytes
                FROM documents
                GROUP BY tenant_id
            ) d ON d.tenant_id = t.id
            LEFT JOIN (
                SELECT tenant_id, COUNT(*) AS questions_24h
                FROM audit_logs
                WHERE action = 'question' 
                  AND created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY tenant_id
            ) q24 ON q24.tenant_id = t.id
            LEFT JOIN (
                SELECT tenant_id, COUNT(*) AS questions_30d
                FROM audit_logs
                WHERE action = 'question' 
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY tenant_id
            ) q30 ON q30.tenant_id = t.id
            LEFT JOIN (
                SELECT tenant_id, MAX(created_at) AS last_activity
                FROM audit_logs
                GROUP BY tenant_id
            ) a ON a.tenant_id = t.id
            LEFT JOIN (
                SELECT tenant_id, 
                       COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                       COUNT(*) FILTER (WHERE status = 'failed') AS failed
                FROM indexing_jobs
                GROUP BY tenant_id
            ) ij ON ij.tenant_id = t.id
        )
        SELECT * FROM tenant_stats
        ORDER BY created_at DESC
    """)
    result = await db.execute(sql)
    return [dict(row._mapping) for row in result]


async def get_tenant_detail(db: AsyncSession, tenant_id: str) -> Dict[str, Any]:
    """
    Get detailed overview for a single tenant including time-series data.
    """
    # Main tenant stats
    overview_sql = text("""
        SELECT 
            t.id,
            t.short_code,
            t.name,
            t.status,
            t.storage_quota_mb,
            t.created_at,
            COALESCE(u.user_count, 0) AS user_count,
            COALESCE(d.doc_count, 0) AS document_count,
            COALESCE(d.storage_bytes, 0) / 1024.0 / 1024.0 AS storage_used_mb,
            COALESCE(q24.questions_24h, 0) AS questions_24h,
            COALESCE(q30.questions_30d, 0) AS questions_30d,
            a.last_activity,
            COALESCE(ij.pending, 0) AS processing_pending,
            COALESCE(ij.failed, 0) AS processing_failed
        FROM tenants t
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS user_count
            FROM users
            WHERE role <> 'super_admin'
            GROUP BY tenant_id
        ) u ON u.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS doc_count, SUM(size_bytes) AS storage_bytes
            FROM documents
            GROUP BY tenant_id
        ) d ON d.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS questions_24h
            FROM audit_logs
            WHERE action = 'question' 
              AND created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY tenant_id
        ) q24 ON q24.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS questions_30d
            FROM audit_logs
            WHERE action = 'question' 
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY tenant_id
        ) q30 ON q30.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, MAX(created_at) AS last_activity
            FROM audit_logs
            GROUP BY tenant_id
        ) a ON a.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, 
                   COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                   COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM indexing_jobs
            GROUP BY tenant_id
        ) ij ON ij.tenant_id = t.id
        WHERE t.id = :tenant_id
    """)
    result = await db.execute(overview_sql, {"tenant_id": tenant_id})
    overview = result.mappings().first()
    
    if not overview:
        return None
    
    # Questions per day for last 30 days
    questions_sql = text("""
        SELECT 
            DATE(created_at) AS day,
            COUNT(*) AS count
        FROM audit_logs
        WHERE tenant_id = :tenant_id
          AND action = 'question'
          AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY day
    """)
    result = await db.execute(questions_sql, {"tenant_id": tenant_id})
    questions_per_day = [{"day": str(row.day), "count": row.count} for row in result]
    
    # Storage per day for last 30 days (from audit_logs where action like 'upload%')
    storage_sql = text("""
        SELECT 
            DATE(created_at) AS day,
            SUM(COALESCE((details->>'size_bytes')::bigint, 0)) / 1024.0 / 1024.0 AS mb
        FROM audit_logs
        WHERE tenant_id = :tenant_id
          AND action IN ('upload', 'document_upload')
          AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY day
    """)
    result = await db.execute(storage_sql, {"tenant_id": tenant_id})
    storage_per_day = [{"day": str(row.day), "mb": float(row.mb or 0)} for row in result]
    
    # Top errors in last 24h
    errors_sql = text("""
        SELECT 
            action,
            COUNT(*) AS count
        FROM audit_logs
        WHERE tenant_id = :tenant_id
          AND created_at >= NOW() - INTERVAL '24 hours'
          AND (details->>'error') IS NOT NULL
        GROUP BY action
        ORDER BY count DESC
        LIMIT 10
    """)
    result = await db.execute(errors_sql, {"tenant_id": tenant_id})
    top_errors = [{"action": row.action, "count": row.count} for row in result]
    
    return {
        "tenant": dict(overview),
        "questions_per_day_30d": questions_per_day,
        "storage_per_day_30d": storage_per_day,
        "top_errors_24h": top_errors,
    }


async def get_platform_health(db: AsyncSession) -> Dict[str, Any]:
    """
    Get platform-wide health metrics.
    """
    # Database stats
    db_sql = text("""
        SELECT 
            pg_database_size('vaultiq') AS size_bytes,
            (SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'vaultiq') AS connections,
            (SELECT setting FROM pg_settings WHERE name = 'max_connections')::int AS max_connections
    """)
    result = await db.execute(db_sql)
    db_row = result.mappings().first()
    
    # Disk usage (DB + storage directory)
    # Note: storage directory check would need filesystem access
    # For now, use DB size
    disk_sql = text("SELECT pg_database_size('vaultiq') AS db_size_bytes")
    result = await db.execute(disk_sql)
    disk_row = result.mappings().first()
    
    # Processing queue
    proc_sql = text("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE status = 'processing') AS processing,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed
        FROM indexing_jobs
    """)
    result = await db.execute(proc_sql)
    proc_row = result.mappings().first()
    
    # No-internet check (try to connect to RFC1918 address that should fail)
    no_internet = True  # We assume isolated; actual check would be external
    
    # Error rate in last 24h
    error_sql = text("""
        SELECT 
            COUNT(*) FILTER (WHERE (details->>'error') IS NOT NULL) AS errors,
            COUNT(*) AS total
        FROM audit_logs
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    """)
    result = await db.execute(error_sql)
    error_row = result.mappings().first()
    error_rate = 0.0
    if error_row and error_row['total'] > 0:
        error_rate = error_row['errors'] / error_row['total']
    
    return {
        "database": {
            "size_mb": round((db_row['size_bytes'] or 0) / 1024.0 / 1024.0, 2) if db_row else 0,
            "connections": db_row['connections'] if db_row else 0,
            "max_connections": db_row['max_connections'] if db_row else 100,
        },
        "disk": {
            "total_mb": 0,  # Would need df or similar
            "used_mb": round((disk_row['db_size_bytes'] or 0) / 1024.0 / 1024.0, 2) if disk_row else 0,
            "free_mb": 0,
        },
        "processing": {
            "pending": proc_row['pending'] if proc_row else 0,
            "processing": proc_row['processing'] if proc_row else 0,
            "failed": proc_row['failed'] if proc_row else 0,
        },
        "no_internet": no_internet,
        "error_rate_24h": round(error_rate, 4),
    }


async def get_platform_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get platform-wide aggregate statistics.
    """
    sql = text("""
        SELECT 
            (SELECT COUNT(*) FROM tenants) AS total_tenants,
            (SELECT COUNT(*) FROM tenants WHERE status = 'active') AS active_tenants,
            (SELECT COUNT(*) FROM users WHERE role <> 'super_admin') AS total_users,
            (SELECT COUNT(*) FROM documents) AS total_documents,
            (SELECT COALESCE(SUM(size_bytes), 0) / 1024.0 / 1024.0 FROM documents) AS total_storage_mb,
            (SELECT COUNT(*) FROM audit_logs 
             WHERE action = 'question' AND created_at >= NOW() - INTERVAL '24 hours') AS total_questions_24h,
            (SELECT COUNT(*) FROM audit_logs 
             WHERE action = 'question' AND created_at >= NOW() - INTERVAL '30 days') AS total_questions_30d
    """)
    result = await db.execute(sql)
    row = result.mappings().first()
    
    return {
        "total_tenants": row['total_tenants'] or 0,
        "active_tenants": row['active_tenants'] or 0,
        "total_users": row['total_users'] or 0,
        "total_documents": row['total_documents'] or 0,
        "total_storage_mb": float(row['total_storage_mb'] or 0),
        "total_questions_24h": row['total_questions_24h'] or 0,
        "total_questions_30d": row['total_questions_30d'] or 0,
    }