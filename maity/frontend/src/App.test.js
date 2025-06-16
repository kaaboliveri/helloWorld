import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios';
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
// global.WebSocket = jest.fn(() => mockWebSocketInstance); // Keep this if App.js uses `new WebSocket` directly
// If App.js uses a ref for WebSocket, we might need to mock the ref or its current property.
// For TestClient.websocket_connect, it handles its own WebSocket interactions.
// The global mock is useful if the App component itself tries to create a WebSocket.
// In our App.js, WebSocket is created in useEffect, so global mock is appropriate.
beforeAll(() => {
    global.WebSocket = jest.fn(() => mockWebSocketInstance);
});


describe('App Component', () => {
    beforeEach(() => {
        axios.post.mockReset();
        // Default GET mock to return empty array to avoid issues with unmocked calls in useEffect
        axios.get.mockReset().mockResolvedValue({ data: [] });
        localStorage.clear();

        mockWebSocketInstance.onopen.mockClear();
        mockWebSocketInstance.onmessage.mockClear();
        mockWebSocketInstance.onerror.mockClear();
        mockWebSocketInstance.onclose.mockClear();
        mockWebSocketInstance.close.mockClear();
        mockWebSocketInstance.send.mockClear();
        // Ensure readyState is reset if changed in a test (though typically not)
        mockWebSocketInstance.readyState = WebSocket.OPEN;
        global.WebSocket.mockClear();
    });

    describe('Monitoring Setup Form', () => {
        test('renders Monitoring tab and setup form', async () => {
            render(<App />);
            fireEvent.click(screen.getByRole('button', { name: /monitoring/i }));
            expect(await screen.findByRole('heading', { name: /automated monitoring setup/i })).toBeInTheDocument();
            // Add more specific checks from previous monitoring tests if needed
            expect(screen.getByLabelText(/topic/i)).toBeInTheDocument();
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
                { topic: 'Test Topic', keywords: 'test, keywords', sources: 'web_search', frequency_hours: 12, }
              );
            });
            expect(await screen.findByText(/success: task 'test topic' successfully set up./i)).toBeInTheDocument();
          });
    });


    describe('View Switching and Basic View Content', () => {
        test('defaults to Chat view and renders chat elements', () => {
            render(<App />);
            expect(screen.getByPlaceholderText('Send a message...')).toBeInTheDocument();
            expect(screen.getByRole('button', {name: /new chat/i})).toBeInTheDocument();
            expect(screen.getByTitle(/select model/i)).toBeInTheDocument();
        });

        test('switches to Monitoring view and renders monitoring elements', async () => {
            render(<App />);
            fireEvent.click(screen.getByRole('button', { name: /monitoring/i }));
            expect(await screen.findByRole('heading', { name: /automated monitoring setup/i })).toBeInTheDocument();
            expect(screen.queryByPlaceholderText('Send a message...')).not.toBeInTheDocument();
        });

        test('switches to App Generator view and renders app generator elements', async () => {
            render(<App />);
            fireEvent.click(screen.getByRole('button', { name: /app generator/i }));
            expect(await screen.findByRole('heading', { name: /application generator/i })).toBeInTheDocument();
            expect(screen.getByPlaceholderText(/describe the application/i)).toBeInTheDocument();
            expect(screen.queryByPlaceholderText('Send a message...')).not.toBeInTheDocument();
        });
    });

    describe('App Generator View Interactions', () => {
        test('submits app generation prompt, sets project ID, and attempts WebSocket connection', async () => {
            axios.post.mockResolvedValueOnce({
                data: { project_id: "new_proj_456", initial_message: "Generation started by API." }
            });

            render(<App />);
            fireEvent.click(screen.getByRole('button', { name: /app generator/i }));

            const promptInput = await screen.findByPlaceholderText(/describe the application/i);
            fireEvent.change(promptInput, { target: { value: 'Create a simple calculator' } });

            const generateButton = screen.getByRole('button', { name: /generate application/i });
            fireEvent.click(generateButton);

            // Check axios call for starting generation
            await waitFor(() => {
                expect(axios.post).toHaveBeenCalledWith(
                    expect.stringContaining('/api/app/generate'),
                    { prompt: 'Create a simple calculator' }
                );
            });

            // Check if UI reflects the initial message from API
            expect(await screen.findByText(/app generation request sent. generation started by api./i)).toBeInTheDocument();
            // Check if Project ID is displayed
            expect(screen.getByText(/project id: new_proj_456/i)).toBeInTheDocument();

            // Check if WebSocket constructor was called for appgen status
            await waitFor(() => {
                expect(global.WebSocket).toHaveBeenCalledWith(expect.stringContaining('/ws/appgen/new_proj_456'));
            });
        });
    });
});
