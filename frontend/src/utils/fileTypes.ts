export const SUPPORTED_FILE_EXTENSIONS = [
  'pdf',
  'md',
  'markdown',
  'txt',
  'json',
  'yaml',
  'yml',
  'csv',
  'html',
  'css',
] as const

export const SUPPORTED_FILE_ACCEPT = [
  ...SUPPORTED_FILE_EXTENSIONS.map((extension) => '.' + extension),
  'application/pdf',
  'text/markdown',
  'text/plain',
  'application/json',
  'application/yaml',
  'text/csv',
  'text/html',
  'text/css',
].join(',')

export function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.slice(dot + 1).toLowerCase() : ''
}

export function isSupportedFile(filename: string): boolean {
  return (SUPPORTED_FILE_EXTENSIONS as readonly string[]).includes(
    fileExtension(filename),
  )
}
