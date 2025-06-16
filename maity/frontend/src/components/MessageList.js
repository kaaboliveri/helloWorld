// In maity/frontend/src/components/MessageList.js
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PrismAsyncLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { jsx, javascript, python, css, shell, sql, yaml, json, markdown as mdLang } from 'react-syntax-highlighter/dist/esm/languages/prism';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

import './MessageList.css';

SyntaxHighlighter.registerLanguage('jsx', jsx);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('js', javascript);
SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('py', python);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('shell', shell);
SyntaxHighlighter.registerLanguage('bash', shell);
SyntaxHighlighter.registerLanguage('sql', sql);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('markdown', mdLang);
SyntaxHighlighter.registerLanguage('md', mdLang);

const CodeBlockWithCopy = ({ language, codeString, inline, className, children, ...props }) => {
    const [isCopied, setIsCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(codeString).then(() => {
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
        }, (err) => {
            console.warn('Failed to copy code to clipboard:', err); // Updated error handling
        });
    };

    if (inline) {
        return <code className="inline-code" {...props}>{children}</code>;
    }

    const detectedLanguage = language || 'plaintext';

    if (detectedLanguage === 'plaintext' && codeString.split('\n').length <= 1 && !className?.includes('language-')) {
         return (
            <div className="code-block-wrapper fallback-wrapper">
                <button onClick={handleCopy} className="copy-code-button simple-copy-button">
                    {isCopied ? 'Copied!' : 'Copy'}
                </button>
                <pre className="fallback-pre simple-pre"><code {...props}>{children}</code></pre>
            </div>
         );
    }

    return (
        <div className="code-block-wrapper">
            <div className="code-block-header">
                <span className="language-name">{detectedLanguage}</span>
                <button onClick={handleCopy} className="copy-code-button">
                    {isCopied ? 'Copied!' : 'Copy'}
                </button>
            </div>
            <SyntaxHighlighter
                style={vscDarkPlus}
                language={detectedLanguage}
                PreTag="div"
                showLineNumbers={detectedLanguage !== 'plaintext' && codeString.split('\n').length > 1}
                wrapLines={true}
                customStyle={{ margin: '0', borderRadius: '0', borderBottomLeftRadius: '5px', borderBottomRightRadius: '5px' }}
                codeTagProps={{ style: { fontSize: '0.9rem', fontFamily: "source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace" } }}
                {...props}
            >
                {codeString}
            </SyntaxHighlighter>
        </div>
    );
};

const MessageList = ({ messages }) => {
  if (!messages || messages.length === 0) {
    return <div className="message-list-empty">No messages yet. Start chatting!</div>;
  }

  const markdownComponents = {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match && match[1] ? match[1] : null;
      const codeString = String(children).replace(/\n$/, '');

      return (
        <CodeBlockWithCopy
          language={language}
          codeString={codeString}
          inline={inline}
          className={className}
          {...props}
        >
          {children}
        </CodeBlockWithCopy>
      );
    },
    a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" /> // Added link renderer
  };

  const renderContent = (text, sender) => {
    const messageText = typeof text === 'string' ? text : String(text || '');
    if (sender === 'ai') {
      const processedText = messageText.replace(/\\n/g, '\n');
      return (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {processedText}
        </ReactMarkdown>
      );
    }
    return messageText.split('\n').map((line, i, arr) => (
        <React.Fragment key={i}>{line}{i < arr.length - 1 && <br />}</React.Fragment>
    ));
  };

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message-item message-from-${msg.sender} ${msg.isError ? 'error-message' : ''} ${msg.isSystemInfo ? 'system-info-message' : ''}`}
        >
          <div className="message-content">
            {renderContent(msg.text, msg.sender)}
          </div>
        </div>
      ))}
    </div>
  );
};

export default MessageList;
