import React, { useState } from 'react';
import './MessageInput.css';

const MessageInput = ({ onSendMessage, isAiTyping }) => { // Added isAiTyping prop
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isAiTyping) { // Prevent send if AI is typing
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="message-input-form">
      <div className="input-wrapper"> {/* Wrapper for centering */}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Send a message..." // Updated placeholder
          className="message-input-field"
          disabled={isAiTyping} // Disable input when AI is typing
        />
        <button
          type="submit"
          className="message-input-button"
          disabled={isAiTyping || !inputValue.trim()} // Disable if AI typing or input empty
        >
          Send
        </button>
      </div>
    </form>
  );
};

export default MessageInput;
