import React from 'react';
import { PrismAsyncLight as SyntaxHighlighter } from 'react-syntax-highlighter';
// Choose a style. `vscDarkPlus` is a good dark theme. Many others are available.
// You might need to selectively import languages to reduce bundle size if using PrismAsyncLight.
// For example, for common languages:
import { jsx, javascript, python, css, shell, sql, yaml, json, markdown } from 'react-syntax-highlighter/dist/esm/languages/prism';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

import './MessageList.css';

// Register languages you want to support
SyntaxHighlighter.registerLanguage('jsx', jsx);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('js', javascript); // common alias
SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('py', python); // common alias
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('shell', shell);
SyntaxHighlighter.registerLanguage('bash', shell); // common alias
SyntaxHighlighter.registerLanguage('sql', sql);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('markdown', markdown);
SyntaxHighlighter.registerLanguage('md', markdown); // common alias


const MessageList = ({ messages }) => {
  if (!messages || messages.length === 0) {
    return <div className="message-list-empty">No messages yet. Start chatting!</div>;
  }

  const renderMessageContent = (text) => {
    // Ensure text is a string
    const messageText = typeof text === 'string' ? text : String(text);
    const parts = messageText.split(/(```(?:[a-z]+)?\n[\s\S]*?\n```)/g); // Regex to split by markdown code blocks

    return parts.map((part, index) => {
      const codeBlockMatch = part.match(/^```([a-z]*)?\n([\s\S]*?)\n```$/); // Regex to extract lang and code
      if (codeBlockMatch) {
        const language = codeBlockMatch[1] || 'plaintext';
        const code = codeBlockMatch[2];
        return (
          <div className="code-block-wrapper" key={`code-${index}`}>
            <SyntaxHighlighter
              language={language}
              style={vscDarkPlus}
              showLineNumbers={language !== 'plaintext' && code.split('\n').length > 1} // Show line numbers for multi-line code (excluding plaintext)
              wrapLines={true}
              customStyle={{ margin: '0', borderRadius: '0' }} // Style for the highlighter component itself, removed individual radius
              codeTagProps={{ style: { fontSize: '0.9rem', fontFamily: "source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace" } }}
            >
              {code}
            </SyntaxHighlighter>
          </div>
        );
      }
      // Render non-code parts, replacing newlines with <br /> for proper display
      // Also handle potential empty strings from split
      if (part.trim() === '') return null;

      return part.split('\n').map((line, i) => (
        <React.Fragment key={`line-${index}-${i}`}>
          {line}
          {i < part.split('\n').length - 1 && <br />}
        </React.Fragment>
      ));
    });
  };

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message-item message-from-${msg.sender} ${msg.isError ? 'error-message' : ''}`}
        >
          <div className="message-content">
            {renderMessageContent(msg.text)}
          </div>
        </div>
      ))}
    </div>
  );
};

export default MessageList;
