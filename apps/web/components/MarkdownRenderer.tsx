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
  a: ({ node: _node, ...props }: AnchorProps) => <a {...props} rel="noreferrer noopener" />,
  pre: ({ node: _node, className, ...props }: PreProps) => (
    <pre className={`code-block ${className ?? ''}`.trim()} {...props} />
  ),
  code: ({ node: _node, inline, className, ...props }: CodeProps) => (
    <code
      className={`${inline ? 'inline-code' : 'code-inline'} ${className ?? ''}`.trim()}
      {...props}
    />
  ),
  table: ({ node: _node, ...props }: TableProps) => (
    <div className="table-wrapper">
      <table {...props} />
    </div>
  ),
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

