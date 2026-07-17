'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

const ALLOWED_PROTOCOLS = ['http:', 'https:', 'mailto:'];

function isAllowedUri(uri: string): string {
  try {
    const parsed = new URL(uri);
    return ALLOWED_PROTOCOLS.includes(parsed.protocol) ? uri : '';
  } catch {
    return '';
  }
}

type Props = {
  content?: string;
  className?: string;
  emptyText?: string;
};

type AnchorProps = React.ComponentPropsWithoutRef<'a'> & { node?: unknown };
type PreProps = React.ComponentPropsWithoutRef<'pre'> & { node?: unknown };
type CodeProps = React.ComponentPropsWithoutRef<'code'> & { inline?: boolean; node?: unknown };
type TableProps = React.ComponentPropsWithoutRef<'table'> & { node?: unknown };

const components = {
  a: ({ node, ...props }: AnchorProps) => {
    void node;
    return <a {...props} rel="noreferrer noopener" />;
  },
  pre: ({ node, className, ...props }: PreProps) => {
    void node;
    return <pre className={`code-block ${className ?? ''}`.trim()} {...props} />;
  },
  code: ({ node, inline, className, ...props }: CodeProps) => {
    void node;
    return (
      <code
        className={`${inline ? 'inline-code' : 'code-inline'} ${className ?? ''}`.trim()}
        {...props}
      />
    );
  },
  table: ({ node, ...props }: TableProps) => {
    void node;
    return (
      <div className="table-wrapper">
        <table {...props} />
      </div>
    );
  },
};

export function MarkdownRenderer({ content, className, emptyText = 'Нет содержимого' }: Props) {
  const text = typeof content === 'string' ? content.trim() : '';
  if (!text) {
    return <div className={className}>{emptyText}</div>;
  }

  return (
    <div className={`markdown-body ${className ?? ''}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        linkTarget="_blank"
        transformLinkUri={isAllowedUri}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
