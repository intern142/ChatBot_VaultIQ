import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FeedbackPanel } from '@/components/feedback';
import { registerMockAnswer, resetMockFeedback } from '@/api/mock/handlers';

describe('FeedbackPanel', () => {
  beforeEach(() => {
    resetMockFeedback();
  });

  it('shows a loading state while fetching existing feedback', () => {
    registerMockAnswer('ans-1');
    render(<FeedbackPanel answerId="ans-1" />);
    expect(screen.getByText('Loading feedback…')).toBeInTheDocument();
  });

  it('submits a vote and comment and shows a success state', async () => {
    registerMockAnswer('ans-1');
    render(<FeedbackPanel answerId="ans-1" />);

    const submitButton = await screen.findByRole('button', { name: /submit feedback/i });
    fireEvent.click(screen.getByLabelText('Thumbs up'));
    expect(screen.getByLabelText('Thumbs up')).toHaveAttribute('aria-pressed', 'true');
    fireEvent.change(screen.getByLabelText('Feedback comment'), {
      target: { value: 'Clear answer' },
    });
    fireEvent.click(submitButton);

    await screen.findByText(/feedback submitted/i);
    expect(screen.getByText(/you voted 👍/i)).toBeInTheDocument();
    expect(screen.getByText(/clear answer/i)).toBeInTheDocument();
  });

  it('lets the user change an existing vote (PATCH path)', async () => {
    registerMockAnswer('ans-1');
    render(<FeedbackPanel answerId="ans-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /submit feedback/i }));
    fireEvent.click(screen.getByLabelText('Thumbs up'));
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    await screen.findByText(/feedback submitted/i);

    fireEvent.click(screen.getByRole('button', { name: /update feedback/i }));
    expect(screen.getByLabelText('Thumbs up')).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByLabelText('Thumbs down'));
    fireEvent.click(screen.getByRole('button', { name: /update feedback/i }));

    await screen.findByText(/you voted 👎/i);
  });

  it('prevents duplicate submissions while one is in flight', async () => {
    registerMockAnswer('ans-1');
    render(<FeedbackPanel answerId="ans-1" />);

    const submitButton = await screen.findByRole('button', { name: /submit feedback/i });
    fireEvent.click(screen.getByLabelText('Thumbs up'));
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    await screen.findByText(/feedback submitted/i);
    // Only one vote exists for this answer: a second POST would have
    // returned 409, and the panel never issues a duplicate create.
    expect(screen.queryByText(/already exists/i)).not.toBeInTheDocument();
  });

  it('reports the contract gap when no answer id is available', async () => {
    render(<FeedbackPanel answerId={null} />);

    fireEvent.click(await screen.findByRole('button', { name: /submit feedback/i }));
    fireEvent.click(screen.getByLabelText('Thumbs up'));
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }));

    await screen.findByText(/did not return an answer id/i);
    expect(screen.queryByText(/feedback submitted/i)).not.toBeInTheDocument();
  });

  it('shows a validation error when no vote is selected', async () => {
    registerMockAnswer('ans-1');
    render(<FeedbackPanel answerId="ans-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /submit feedback/i }));

    await screen.findByText(/choose thumbs up or thumbs down/i);
  });
});
