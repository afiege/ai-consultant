import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ChatMessage = ({ message, collaborativeMode = false }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        {collaborativeMode && message.participant_name && isUser && (
          <p className="text-xs font-semibold mb-1 opacity-80">
            {message.participant_name}
          </p>
        )}
        <div className="text-sm">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
              ul: ({ children }) => (
                <ul className={`list-disc ml-4 mb-3 ${isUser ? 'text-white' : ''}`}>
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className={`list-decimal ml-4 mb-3 ${isUser ? 'text-white' : ''}`}>
                  {children}
                </ol>
              ),
              li: ({ children }) => <li className="mb-1">{children}</li>,
              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
              em: ({ children }) => <em className="italic">{children}</em>,
              h1: ({ children }) => (
                <h1 className={`text-lg font-bold mb-2 mt-4 first:mt-0 ${isUser ? 'text-white' : 'text-gray-900'}`}>
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className={`text-base font-bold mb-2 mt-4 first:mt-0 ${isUser ? 'text-white' : 'text-gray-900'}`}>
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className={`text-sm font-bold mb-2 mt-4 first:mt-0 ${isUser ? 'text-white' : 'text-gray-900'}`}>
                  {children}
                </h3>
              ),
              h4: ({ children }) => (
                <h4 className={`text-sm font-semibold mb-2 mt-3 first:mt-0 ${isUser ? 'text-white' : 'text-gray-900'}`}>
                  {children}
                </h4>
              ),
              code: ({ inline, children }) =>
                inline ? (
                  <code
                    className={`px-1 py-0.5 rounded text-xs font-mono ${
                      isUser ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    {children}
                  </code>
                ) : (
                  <code
                    className={`block p-2 rounded text-xs font-mono my-2 overflow-x-auto ${
                      isUser ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    {children}
                  </code>
                ),
              blockquote: ({ children }) => (
                <blockquote
                  className={`border-l-4 pl-3 my-2 italic ${
                    isUser ? 'border-blue-300 text-blue-100' : 'border-gray-300 text-gray-600'
                  }`}
                >
                  {children}
                </blockquote>
              ),
              hr: () => (
                <hr className={`my-3 ${isUser ? 'border-blue-400' : 'border-gray-300'}`} />
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
