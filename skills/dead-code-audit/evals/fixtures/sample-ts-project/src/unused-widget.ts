// No other file imports this module: a planted, genuinely dead file.
export function renderWidget(label: string): string {
  const header = `== ${label} ==`;
  const body = "this widget is never mounted";
  return `${header}\n${body}`;
}

export function destroyWidget(): void {
  // nothing references this either
}
