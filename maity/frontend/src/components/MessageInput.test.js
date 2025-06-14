import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MessageInput from './MessageInput';

describe('MessageInput Component', () => {
  test('renders input field and send button', () => {
    render(<MessageInput onSendMessage={() => {}} isAiTyping={false} />);
    expect(screen.getByPlaceholderText('Send a message...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  test('input value changes when user types', () => {
    render(<MessageInput onSendMessage={() => {}} isAiTyping={false} />);
    const inputField = screen.getByPlaceholderText('Send a message...');
    fireEvent.change(inputField, { target: { value: 'Hello test' } });
    expect(inputField.value).toBe('Hello test');
  });

  test('calls onSendMessage with input value when form is submitted', () => {
    const mockOnSendMessage = jest.fn();
    render(<MessageInput onSendMessage={mockOnSendMessage} isAiTyping={false} />);
    const inputField = screen.getByPlaceholderText('Send a message...');
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(inputField, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    expect(mockOnSendMessage).toHaveBeenCalledTimes(1);
    expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
    expect(inputField.value).toBe(''); // Input should clear after send
  });

  test('does not call onSendMessage if input is empty or only whitespace', () => {
    const mockOnSendMessage = jest.fn();
    render(<MessageInput onSendMessage={mockOnSendMessage} isAiTyping={false} />);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Check initial state for empty input
    expect(sendButton).toBeDisabled(); // Button should be disabled if input is empty

    fireEvent.click(sendButton); // Click with empty input
    expect(mockOnSendMessage).not.toHaveBeenCalled();

    const inputField = screen.getByPlaceholderText('Send a message...');
    fireEvent.change(inputField, { target: { value: '   ' } }); // Input with only whitespace
    // Button should still be disabled for whitespace only
    expect(sendButton).toBeDisabled();
    fireEvent.click(sendButton);
    expect(mockOnSendMessage).not.toHaveBeenCalled();
  });

  test('send button is disabled when input is empty, enabled when not', () => {
    render(<MessageInput onSendMessage={() => {}} isAiTyping={false} />);
    const sendButton = screen.getByRole('button', { name: /send/i });
    expect(sendButton).toBeDisabled();

    const inputField = screen.getByPlaceholderText('Send a message...');
    fireEvent.change(inputField, { target: { value: 'not empty' } });
    expect(sendButton).not.toBeDisabled();

    fireEvent.change(inputField, { target: { value: '' } }); // Back to empty
    expect(sendButton).toBeDisabled();
  });

  test('input field and send button are disabled when isAiTyping is true', () => {
    render(<MessageInput onSendMessage={() => {}} isAiTyping={true} />);
    const inputField = screen.getByPlaceholderText('Send a message...');
    const sendButton = screen.getByRole('button', { name: /send/i });

    expect(inputField).toBeDisabled();
    expect(sendButton).toBeDisabled();
  });
});
