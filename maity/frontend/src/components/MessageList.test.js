// maity/frontend/src/components/MessageList.test.js
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import MessageList from './MessageList';

// Mock react-syntax-highlighter
// We are testing if MessageList passes the correct props, not the highlighter itself.
const mockSyntaxHighlighterProps = jest.fn();
jest.mock('react-syntax-highlighter', () => ({
  PrismAsyncLight: jest.fn((props) => {
    mockSyntaxHighlighterProps(props); // Capture props passed to SyntaxHighlighter
    // Render children directly for content checking, or a simplified pre/code structure
    return (
      <pre data-testid="syntax-highlighter" data-language={props.language}>
        <code>{props.children}</code>
      </pre>
    );
  }),
}));
// Mock individual language imports for SyntaxHighlighter
jest.mock('react-syntax-highlighter/dist/esm/languages/prism', () => ({
    jsx: jest.fn(), javascript: jest.fn(), python: jest.fn(), css: jest.fn(),
    shell: jest.fn(), sql: jest.fn(), yaml: jest.fn(), json: jest.fn(), markdown: jest.fn()
}));
// Mock style import for SyntaxHighlighter
jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
    vscDarkPlus: {}
}));

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockResolvedValue(undefined),
  },
});

describe('MessageList Component', () => {
  const baseMessages = [
    { id: 1, text: 'Hello user', sender: 'user', isError: false, isSystemInfo: false },
    { id: 2, text: 'Hi there, AI here!', sender: 'ai', isError: false, isSystemInfo: false },
  ];

  beforeEach(() => {
    navigator.clipboard.writeText.mockClear();
    mockSyntaxHighlighterProps.mockClear(); // Clear calls to SyntaxHighlighter mock
    // Clear any other mocks if necessary
  });

  test('renders "No messages yet" when messages array is empty', () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByText('No messages yet. Start chatting!')).toBeInTheDocument();
  });

  test('renders a list of messages', () => {
    render(<MessageList messages={baseMessages} />);
    expect(screen.getByText('Hello user')).toBeInTheDocument();
    // AI messages are processed by ReactMarkdown, which might wrap text in <p>
    expect(screen.getByText('Hi there, AI here!', { selector: 'p' })).toBeInTheDocument();
  });

  test('applies correct sender class (user/ai)', () => {
    render(<MessageList messages={baseMessages} />);
    const userMessage = screen.getByText('Hello user').closest('.message-item');
    expect(userMessage).toHaveClass('message-from-user');

    const aiMessage = screen.getByText('Hi there, AI here!', { selector: 'p' }).closest('.message-item');
    expect(aiMessage).toHaveClass('message-from-ai');
  });

  test('renders AI message with Markdown (bold, italic)', () => {
    const messagesWithMarkdown = [
      { id: 1, text: 'This is **bold** and *italic*.', sender: 'ai' }
    ];
    render(<MessageList messages={messagesWithMarkdown} />);
    const boldText = screen.getByText('bold', { selector: 'strong' });
    const italicText = screen.getByText('italic', { selector: 'em' });
    expect(boldText).toBeInTheDocument();
    expect(italicText).toBeInTheDocument();
  });

  test('renders AI message with code block and calls SyntaxHighlighter with correct props', () => {
    const codeContent = 'print("Hello")';
    const messagesWithCode = [
      { id: 1, text: `\`\`\`python\n${codeContent}\n\`\`\``, sender: 'ai' }
    ];
    render(<MessageList messages={messagesWithCode} />);

    expect(screen.getByTestId('syntax-highlighter')).toBeInTheDocument();
    expect(mockSyntaxHighlighterProps).toHaveBeenCalledWith(
      expect.objectContaining({
        language: 'python',
        children: codeContent, // SyntaxHighlighter receives the raw code string
        style: expect.any(Object), // vscDarkPlus mock
      })
    );
    expect(screen.getByText(codeContent)).toBeInTheDocument();
  });

  test('renders AI message with inline code', () => {
    const messagesWithInlineCode = [
      { id: 1, text: 'Use `Array.map()` for this.', sender: 'ai' }
    ];
    render(<MessageList messages={messagesWithInlineCode} />);
    const inlineCode = screen.getByText('Array.map()', { selector: 'code.inline-code' });
    expect(inlineCode).toBeInTheDocument();
  });

  test('copy button appears for code blocks and copies content', async () => {
    jest.useFakeTimers();
    const codeContent = 'print("Copy me")';
    const messagesWithCode = [
      { id: 1, text: `\`\`\`python\n${codeContent}\n\`\`\``, sender: 'ai' }
    ];
    render(<MessageList messages={messagesWithCode} />);

    const copyButton = screen.getByRole('button', { name: /copy/i });
    expect(copyButton).toBeInTheDocument();

    fireEvent.click(copyButton);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(codeContent);
    expect(screen.getByRole('button', { name: /copied!/i })).toBeInTheDocument();

    act(() => {
        jest.advanceTimersByTime(2000);
    });

    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();

    jest.useRealTimers();
  });

  test('renders system info message with correct class', () => {
    const messages = [{ id: 1, text: 'Switched model.', sender: 'ai', isSystemInfo: true }];
    render(<MessageList messages={messages} />);
    // System info text might be wrapped in <p> by ReactMarkdown
    const systemMessageText = screen.getByText('Switched model.', { selector: 'p' });
    const systemMessageItem = systemMessageText.closest('.message-item');
    expect(systemMessageItem).toHaveClass('system-info-message');
  });

  test('renders error message with correct class', () => {
    const messages = [{ id: 1, text: 'An error occurred.', sender: 'ai', isError: true }];
    render(<MessageList messages={messages} />);
    const errorMessageText = screen.getByText('An error occurred.', { selector: 'p' });
    const errorMessageItem = errorMessageText.closest('.message-item');
    expect(errorMessageItem).toHaveClass('error-message');
  });

});
