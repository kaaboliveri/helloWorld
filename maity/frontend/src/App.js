import React, { useState, useEffect, useRef } from 'react'; // Added useRef
// Remove axios import if all chat communication goes via WebSocket
// import axios from 'axios';
import './App.css';
import MessageList from './components/MessageList';
import MessageInput from './components/MessageInput';

let messageIdCounter = 2; // Adjusted as initial messages changed
const BACKEND_WS_URL = process.env.REACT_APP_BACKEND_WS_URL || 'ws://localhost:8000/ws/chat';

function App() {
  const [messages, setMessages] = useState([
    { id: 1, text: 'Hello! I am Maity. Ask me anything.', sender: 'ai' },
  ]);
  const [conversationId, setConversationId] = useState(() => {
    // Attempt to retrieve conversationId from localStorage or generate a new one
    const savedCid = localStorage.getItem('maityConversationId');
    return savedCid || `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  });
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [error, setError] = useState(null);
  const webSocket = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  // Effect to store conversationId in localStorage
  useEffect(() => {
    if (conversationId) {
      localStorage.setItem('maityConversationId', conversationId);
    }
  }, [conversationId]);

  // Effect for WebSocket connection management
  useEffect(() => {
    if (!conversationId) return;

    console.log(`Attempting to connect WebSocket for conversation: ${conversationId}`);
    const wsUrl = `${BACKEND_WS_URL}/${conversationId}`;
    webSocket.current = new WebSocket(wsUrl);

    webSocket.current.onopen = () => {
      console.log('WebSocket connected to:', wsUrl);
      setIsConnected(true);
      setError(null); // Clear previous connection errors
      // Optionally, send a message to confirm connection or fetch history if backend supports
    };

    webSocket.current.onmessage = (event) => {
      setIsAiTyping(false); // Assume AI stops typing once a message is received
      try {
        const receivedData = JSON.parse(event.data);
        console.log('WebSocket message received:', receivedData);

        if (receivedData.type === 'error') {
          setError(receivedData.content || 'An error occurred via WebSocket.');
          const errorMessage = {
            id: messageIdCounter++,
            text: `Error: ${receivedData.content}`,
            sender: 'ai',
            isError: true,
          };
          setMessages(prevMessages => [...prevMessages, errorMessage]);
        } else if (receivedData.type === 'status') {
          // Could be used for more granular "thinking" steps
          // For now, just log it or show a subtle status
          console.log("Status update:", receivedData.content);
          if (receivedData.content.toLowerCase().includes("processing") || receivedData.content.toLowerCase().includes("thinking")) {
            setIsAiTyping(true);
          }
        } else if (receivedData.type === 'final_response') {
          const aiResponseMessage = {
            id: messageIdCounter++,
            text: receivedData.content,
            sender: 'ai',
            isError: receivedData.error || false,
            // debug_info: receivedData.debug_info // if needed
          };
          setMessages(prevMessages => [...prevMessages, aiResponseMessage]);
          if (receivedData.debug_info && receivedData.debug_info.model_used) {
            // Optionally display model used or other debug info
          }
        } else if (receivedData.type === 'stream_chunk' || receivedData.type === 'agent_thought') { // Example for streaming
            setIsAiTyping(true);
            setMessages(prevMessages => {
                const lastMessage = prevMessages[prevMessages.length - 1];
                // Check if last message has a streaming ID or if it's a new stream
                const streamMessageId = receivedData.message_id || (lastMessage && lastMessage.isStreaming ? lastMessage.id : messageIdCounter);

                if (lastMessage && lastMessage.sender === 'ai' && lastMessage.id === streamMessageId && lastMessage.isStreaming) {
                    // Append to existing AI message for streaming
                    return [
                        ...prevMessages.slice(0, -1),
                        { ...lastMessage, text: lastMessage.text + receivedData.content }
                    ];
                } else {
                    // Start a new AI message for streaming
                    if (lastMessage && lastMessage.id === streamMessageId && lastMessage.isStreaming) { // Should not happen if IDs are managed well
                         // This case is tricky, means we got a new chunk for an ID that wasn't the last one.
                         // For simplicity, we'll just append a new message. Better handling might be needed.
                         console.warn("Streaming to a non-last message, creating new bubble.")
                    }
                    if (streamMessageId === messageIdCounter) messageIdCounter++; // Increment if we used the global counter

                    return [
                        ...prevMessages,
                        { id: streamMessageId, text: receivedData.content, sender: 'ai', isStreaming: true }
                    ];
                }
            });
        } else if (receivedData.type === 'stream_end') {
             setIsAiTyping(false);
             setMessages(prevMessages => prevMessages.map(msg => msg.id === receivedData.message_id ? {...msg, isStreaming: false} : msg ));
        }


        // Update conversation ID if backend provides a new one (e.g. after first message)
        // This should ideally happen on connection or a specific handshake message
        if (receivedData.conversation_id && receivedData.conversation_id !== conversationId) {
          setConversationId(receivedData.conversation_id);
        }

      } catch (e) {
        console.error('Error processing WebSocket message:', e);
        setError('Received malformed data from server.');
      }
    };

    webSocket.current.onerror = (err) => {
      console.error('WebSocket error:', err);
      setError('WebSocket connection error. Please try refreshing. Is the backend running and accessible?');
      setIsAiTyping(false);
      setIsConnected(false);
    };

    webSocket.current.onclose = (event) => {
      console.log('WebSocket disconnected:', event.reason, `Code: ${event.code}`);
      setIsConnected(false);
      if (!event.wasClean) {
        //setError('WebSocket connection closed unexpectedly. Attempting to reconnect or refresh.');
      }
      // Optionally, implement reconnection logic here
    };

    return () => {
      if (webSocket.current) {
        console.log("Closing WebSocket connection");
        webSocket.current.close();
      }
    };
  }, [conversationId]); // Reconnect if conversationId changes

  const handleSendMessage = async (text) => {
    if (!webSocket.current || webSocket.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to Maity AI. Please wait or refresh.');
      // Optionally, try to reconnect or queue the message
      return;
    }

    const newUserMessage = {
      id: messageIdCounter++,
      text: text,
      sender: 'user',
    };
    setMessages(prevMessages => [...prevMessages, newUserMessage]);
    setIsAiTyping(true);
    setError(null);

    try {
      const messagePayload = {
        message: text,
        // config: { preferred_model: "o3-mini" } // Example config if needed
      };
      webSocket.current.send(JSON.stringify(messagePayload));
      console.log('WebSocket message sent:', messagePayload);
    } catch (err) {
      console.error('Error sending message via WebSocket:', err);
      setError('Failed to send message. Check connection.');
      setIsAiTyping(false);
    }
  };

  useEffect(() => {
    const messageList = document.querySelector('.message-list');
    if (messageList) {
      messageList.scrollTop = messageList.scrollHeight;
    }
  }, [messages]);

  // Function to start a new chat
  const handleNewChat = () => {
    if (webSocket.current) {
      webSocket.current.close(); // Close existing connection
    }
    setMessages([{ id: 1, text: 'New chat started. How can I help?', sender: 'ai' }]);
    // Generate a new conversation ID to trigger WebSocket reconnection
    setConversationId(`local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
    setIsAiTyping(false);
    setError(null);
    messageIdCounter = 2; // Reset counter for new chat
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Maity AI Chat</h1>
        <button onClick={handleNewChat} className="new-chat-button">New Chat</button>
      </header>
      <div className="chat-window">
        {!isConnected && !error && <div className="connection-indicator">Connecting to Maity...</div>}
        {/* Display general errors only if not a WebSocket connection error already shown by isConnected=false */}
        {error && isConnected && <div className="error-indicator">{error}</div>}
        <MessageList messages={messages} />
        {isAiTyping && <div className="typing-indicator">Maity is thinking...</div>}
        <MessageInput onSendMessage={handleSendMessage} isAiTyping={isAiTyping || !isConnected} />
      </div>
    </div>
  );
}

export default App;
