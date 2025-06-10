import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PrismAsyncLight as SyntaxHighlighter } from 'react-syntax-highlighter';
// Renamed markdown to mdLang to avoid conflict with the 'markdown' variable from SyntaxHighlighter.registerLanguage
import { jsx, javascript, python, css, shell, sql, yaml, json, markdown as mdLang } from 'react-syntax-highlighter/dist/esm/languages/prism';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

import './MessageList.css';

// Register languages for SyntaxHighlighter
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
SyntaxHighlighter.registerLanguage('markdown', mdLang);
SyntaxHighlighter.registerLanguage('md', mdLang); // common alias


const MessageList = ({ messages }) => {
  if (!messages || messages.length === 0) {
    return <div className="message-list-empty">No messages yet. Start chatting!</div>;
  }

  // Custom renderer for code blocks within ReactMarkdown
  const markdownComponents = {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match && match[1] ? match[1] : 'plaintext';
      // Ensure children is an array and join, then trim. Handle case where children might be just a string.
      const codeString = Array.isArray(children) ? children.join('') : String(children);
      const trimmedCodeString = codeString.replace(/\n$/, '');


      if (inline) { // Handle inline code
        return <code className="inline-code" {...props}>{children}</code>;
      }

      return !inline && match ? (
        <div className="code-block-wrapper">
          {/* Optional: Add a language label here if desired */}
          {/* <div className="code-block-language-label">{language}</div> */}
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={language}
            PreTag="div" // Use div instead of pre to avoid nesting pre tags if react-markdown wraps in one
            showLineNumbers={language !== 'plaintext' && trimmedCodeString.split('\n').length > 1}
            wrapLines={true}
            customStyle={{ margin: '0', borderRadius: '0' }} // Overwrite default margin of pre from highlighter
            codeTagProps={{ style: { fontSize: '0.9rem', fontFamily: "source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace" } }}
            {...props}
          >
            {trimmedCodeString}
          </SyntaxHighlighter>
        </div>
      ) : (
         // Fallback for code blocks without a language or other issues (should be rare with GFM)
        <pre className="code-block-wrapper fallback-pre"><code className={className} {...props}>{children}</code></pre>
      );
    }
  };

  const renderMessageContent = (text) => {
    // Ensure text is a string
    const messageText = typeof text === 'string' ? text : String(text);
    // Replace escaped newlines \n with actual newlines before passing to Markdown parser
    // This is important if the AI sends text with double-escaped newlines.
    const processedText = messageText.replace(/\\n/g, '\n');

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {processedText}
      </ReactMarkdown>
    );
  };


  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message-item message-from-${msg.sender} ${msg.isError ? 'error-message' : ''} ${msg.isSystemInfo ? 'system-info-message' : ''}`}
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
