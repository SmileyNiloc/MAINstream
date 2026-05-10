from ctk_markdown import CTkMarkdown


class textDisplay(CTkMarkdown):
    '''
    Markdown-rendering text display backed by ctk-markdown.
    Keeps the small app-specific API used by the rest of the codebase.
    '''

    def __init__(self, master=None, markdown_text='', **kwargs):
        kwargs.setdefault('wrap', 'word')
        super().__init__(master, markdown_text=markdown_text, **kwargs)
        self._markdown_buffer = markdown_text or ''

    def add_text(self, text):
        '''
        Replace the current content with Markdown text.
        '''
        if isinstance(text, list):
            text = '\n'.join(str(item) for item in text)
        elif text is None:
            text = ''
        else:
            text = str(text)

        self._markdown_buffer = text
        self.set_markdown(self._markdown_buffer)

    def append_text(self, text):
        '''
        Append Markdown text and re-render the buffer.
        '''
        if text is None:
            return
        self._markdown_buffer += str(text)
        self.set_markdown(self._markdown_buffer)
