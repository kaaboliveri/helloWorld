import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios'; // To mock axios
import App from './App';

// Mock axios
jest.mock('axios');

// Mock WebSocket
const mockWebSocketInstance = {
    onopen: jest.fn(),
    onmessage: jest.fn(),
    onerror: jest.fn(),
    onclose: jest.fn(),
    close: jest.fn(),
    send: jest.fn(),
    readyState: WebSocket.OPEN, // Simulate open state for relevant tests
};
global.WebSocket = jest.fn(() => mockWebSocketInstance);


describe('App Component - Monitoring Setup Form', () => {
  beforeEach(() => {
    // Reset mocks before each test
    axios.post.mockReset();
    axios.get.mockReset();
    localStorage.clear();

    // Clear all mock call counts and implementations for WebSocket instance methods
    mockWebSocketInstance.onopen.mockClear();
    mockWebSocketInstance.onmessage.mockClear();
    mockWebSocketInstance.onerror.mockClear();
    mockWebSocketInstance.onclose.mockClear();
    mockWebSocketInstance.close.mockClear();
    mockWebSocketInstance.send.mockClear();
    // Reset the WebSocket constructor mock itself if needed (e.g. to check number of connections)
    global.WebSocket.mockClear();
    // Re-assign a fresh mock instance for each test if state needs to be fully isolated
    // For now, clearing method calls on the shared instance is often sufficient.
    // To be absolutely sure:
    // global.WebSocket = jest.fn(() => ({ ...mockWebSocketInstance })); // Creates new object with same mock fns
  });

  test('renders Monitoring tab and setup form when Monitoring view is active', async () => {
    render(<App />);
    const monitoringTabButton = screen.getByRole('button', { name: /monitoring/i });
    fireEvent.click(monitoringTabButton);

    expect(await screen.findByRole('heading', { name: /automated monitoring setup/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/topic/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/keywords\/query/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /setup monitoring task/i })).toBeInTheDocument();
  });

  test('allows input in monitoring setup form fields', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /monitoring/i }));

    const topicInput = await screen.findByLabelText(/topic/i);
    fireEvent.change(topicInput, { target: { value: 'Test Topic' } });
    expect(topicInput.value).toBe('Test Topic');

    const keywordsInput = screen.getByLabelText(/keywords\/query/i);
    fireEvent.change(keywordsInput, { target: { value: 'test, keywords' } });
    expect(keywordsInput.value).toBe('test, keywords');

    const frequencyInput = screen.getByLabelText(/frequency \(hours\)/i);
    fireEvent.change(frequencyInput, { target: { value: '12' } });
    expect(frequencyInput.value).toBe('12');
  });

  test('submits monitoring setup form data and displays success message', async () => {
    axios.post.mockResolvedValueOnce({
        data: { message: "Task 'Test Topic' successfully set up." }
    });
    axios.get.mockResolvedValueOnce({ data: [] }); // For fetchActiveMonitorTasks

    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /monitoring/i }));

    const topicInput = await screen.findByLabelText(/topic/i);

    fireEvent.change(topicInput, { target: { value: 'Test Topic' } });
    fireEvent.change(screen.getByLabelText(/keywords\/query/i), { target: { value: 'test, keywords' } });
    fireEvent.change(screen.getByLabelText(/frequency \(hours\)/i), { target: { value: '12' } });

    fireEvent.click(screen.getByRole('button', { name: /setup monitoring task/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/monitor/setup'),
        {
          topic: 'Test Topic',
          keywords: 'test, keywords',
          sources: 'web_search',
          frequency_hours: 12,
        }
      );
    });

    expect(await screen.findByText(/success: task 'test topic' successfully set up./i)).toBeInTheDocument();
  });


  test('displays error message if monitoring setup form submission fails', async () => {
    axios.post.mockRejectedValueOnce({
        response: { data: { detail: "Backend validation failed." } }
    });

    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /monitoring/i }));

    const topicInput = await screen.findByLabelText(/topic/i);

    fireEvent.change(topicInput, { target: { value: 'Error Topic' } });
    fireEvent.change(screen.getByLabelText(/keywords\/query/i), { target: { value: 'error test' } });
    fireEvent.change(screen.getByLabelText(/frequency \(hours\)/i), { target: { value: '10' } });

    fireEvent.click(screen.getByRole('button', { name: /setup monitoring task/i }));

    expect(await screen.findByText(/error: backend validation failed./i)).toBeInTheDocument();
  });
});
