/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { FileText, FileCode, Image, Table, ExternalLink, Folder } from 'lucide-react';
import './FileCard.css';

const EXT_ICONS: Record<string, LucideIcon> = {
  py: FileCode, js: FileCode, jsx: FileCode, ts: FileCode, tsx: FileCode,
  html: FileCode, css: FileCode, sh: FileCode, bash: FileCode, sql: FileCode,
  csv: Table, json: Table, yaml: Table, yml: Table, xml: Table, toml: Table, xlsx: Table, xls: Table,
  png: Image, jpg: Image, jpeg: Image, svg: Image, gif: Image, webp: Image,
};

export const KNOWN_EXTS = new Set([
  'md', 'txt', 'pdf', 'doc', 'docx', 'rtf',
  'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'sh', 'bash', 'sql', 'r', 'ipynb',
  'csv', 'json', 'yaml', 'yml', 'xml', 'toml', 'ini', 'cfg', 'log', 'env', 'xlsx', 'xls',
  'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp',
  'zip', 'tar', 'gz',
]);

/**
 * Check if an href looks like a sandbox file path (not an external URL).
 */
export function isFilePath(href: string | undefined): boolean {
  if (!href || href.startsWith('http') || href.startsWith('//') || href.startsWith('mailto:') || href.startsWith('#')) return false;
  const ext = href.split('.').pop()?.split(/[?#]/)[0]?.toLowerCase();
  return !!ext && KNOWN_EXTS.has(ext);
}

/**
 * Normalize a sandbox file path: strip /home/workspace/ prefix.
 */
export function normalizeFilePath(path: string): string {
  return path.replace(/^\/home\/workspace\//, '');
}

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp']);

/**
 * Check if an href points to an image file.
 */
export function isImagePath(href: string | undefined): boolean {
  if (!href) return false;
  const ext = href.split('.').pop()?.split(/[?#]/)[0]?.toLowerCase();
  return !!ext && IMAGE_EXTS.has(ext);
}

/**
 * Extract file paths from message text.
 * Matches patterns like dir/file.ext, dir/subdir/file.ext, /home/workspace/results/file.ext.
 * Requires at least one `/` and a known file extension to avoid false positives.
 */
export function extractFilePaths(text: string | undefined): string[] {
  if (!text) return [];
  // Match paths: must have at least one /, end with .extension
  // Handles relative (dir/file.ext) and absolute (/home/workspace/file.ext) paths
  // Handles paths in backticks, quotes, or bare
  const regex = /(?:^|[\s`"'([])(\/[a-zA-Z_][^\s`"')\]<>]*\/[^\s`"')\]<>]*\.[a-zA-Z0-9]{1,10}|[a-zA-Z_][^\s`"')\]<>]*\/[^\s`"')\]<>]*\.[a-zA-Z0-9]{1,10})(?=[\s`"')\],:;!?|]|$)/gm;
  const paths = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    let path = match[1];
    // Trim trailing punctuation
    path = path.replace(/[,:;!?]+$/, '');
    const ext = path.split('.').pop()!.toLowerCase();
    if (!KNOWN_EXTS.has(ext)) continue;
    // Skip URLs
    if (path.startsWith('http') || path.startsWith('www.') || path.startsWith('//')) continue;
    // Normalize absolute sandbox paths to relative
    path = path.replace(/^\/home\/workspace\//, '');
    paths.add(path);
  }
  return Array.from(paths);
}

interface FileCardProps {
  path: string;
  onOpen: () => void;
}

function FileCard({ path, onOpen }: FileCardProps): React.ReactElement {
  const ext = path.split('.').pop()!.toLowerCase();
  const fileName = path.split('/').pop();
  const dirPath = path.split('/').slice(0, -1).join('/');
  const Icon = EXT_ICONS[ext] || FileText;

  return (
    <button className="file-mention-card" onClick={onOpen} title={`Open ${path}`}>
      <Icon className="file-mention-card-icon" />
      <div className="file-mention-card-info">
        <span className="file-mention-card-name">{fileName}</span>
        {dirPath && <span className="file-mention-card-dir">{dirPath}/</span>}
      </div>
      <ExternalLink className="file-mention-card-action" />
    </button>
  );
}

interface DirCardProps {
  dir: string;
  fileCount: number;
  onOpen: () => void;
}

function DirCard({ dir, fileCount, onOpen }: DirCardProps): React.ReactElement {
  return (
    <button className="file-mention-card file-mention-card-dir-card" onClick={onOpen} title={`Open ${dir}/ in file panel`}>
      <Folder className="file-mention-card-icon" />
      <div className="file-mention-card-info">
        <span className="file-mention-card-name">{dir}/</span>
        <span className="file-mention-card-dir">{fileCount} file{fileCount !== 1 ? 's' : ''}</span>
      </div>
      <ExternalLink className="file-mention-card-action" />
    </button>
  );
}

interface FileMentionCardsProps {
  filePaths: string[] | null;
  onOpenFile: (path: string) => void;
  onOpenDir?: (dir: string) => void;
}

/**
 * Renders file mention cards below a message.
 * If <= 5 files: show individual file cards.
 * If > 5 files: group by top-level directory, show dir cards + root file cards.
 */
export function FileMentionCards({ filePaths, onOpenFile, onOpenDir }: FileMentionCardsProps): React.ReactElement | null {
  if (!filePaths || filePaths.length === 0) return null;

  if (filePaths.length <= 5) {
    return (
      <div className="file-mention-cards">
        {filePaths.map((path) => (
          <FileCard key={path} path={path} onOpen={() => onOpenFile(path)} />
        ))}
      </div>
    );
  }

  // Group by top-level directory
  const groups: Record<string, string[]> = {};
  const rootFiles: string[] = [];
  for (const path of filePaths) {
    const parts = path.split('/');
    if (parts.length > 1) {
      const dir = parts[0];
      if (!groups[dir]) groups[dir] = [];
      groups[dir].push(path);
    } else {
      rootFiles.push(path);
    }
  }

  // Sort directories: results -> data -> rest alphabetical
  const dirPriority: Record<string, number> = { results: 0, data: 1 };
  const sortedDirs = Object.entries(groups).sort(([a], [b]) => {
    const pa = dirPriority[a] ?? 2;
    const pb = dirPriority[b] ?? 2;
    if (pa !== pb) return pa - pb;
    return a.localeCompare(b);
  });

  return (
    <div className="file-mention-cards">
      {rootFiles.map((path) => (
        <FileCard key={path} path={path} onOpen={() => onOpenFile(path)} />
      ))}
      {sortedDirs.map(([dir, files]) => (
        <DirCard
          key={dir}
          dir={dir}
          fileCount={files.length}
          onOpen={() => onOpenDir ? onOpenDir(dir) : onOpenFile(files[0])}
        />
      ))}
    </div>
  );
}

export default FileCard;
