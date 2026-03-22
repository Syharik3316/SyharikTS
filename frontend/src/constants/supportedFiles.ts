export const SUPPORTED_FILE_EXTENSIONS = [
  "csv",
  "xls",
  "xlsx",
  "pdf",
  "docx",
  "png",
  "jpg",
  "jpeg",
  "tif",
  "tiff",
  "txt",
  "md",
  "rtf",
  "odt",
  "xml",
  "epub",
  "fb2",
  "doc",
] as const;

export const ACCEPT_ATTR =
  ".csv,.xls,.xlsx,.pdf,.docx,.doc,.png,.jpg,.jpeg,.tif,.tiff,.txt,.md,.rtf,.odt,.xml,.epub,.fb2,text/plain,text/markdown,text/rtf,text/xml,application/xml,application/rtf,application/msword,application/epub+zip,application/vnd.oasis.opendocument.text,application/x-fictionbook+xml,image/png,image/jpeg,image/tiff,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export const SUPPORTED_EXT_SET = new Set<string>(SUPPORTED_FILE_EXTENSIONS);
