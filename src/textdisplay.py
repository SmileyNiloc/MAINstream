import customtkinter


class textDisplay(customtkinter.CTkTextbox):
    '''
    A custom text display widget that is read-only and can be used to display text in the app
    '''

    def __init__(self, master=None, ** kwargs):
        super().__init__(
            master,
            corner_radius=14,
            border_width=1,
            border_color=("#D1D5DB", "#374151"),
            fg_color=("#FFFFFF", "#1F2937"),
            text_color="#111827",
            scrollbar_button_color=("#9CA3AF", "#6B7280"),
            scrollbar_button_hover_color=("#6B7280", "#9CA3AF"),
            font=("Segoe UI", 13),
            wrap="word",
            **kwargs,
        )
        # Make it read-only
        self.configure(state="disabled")

    def add_text(self, text):
        '''
        Add text to the text display widget
        '''
        # Have to temporarily make it editable to add text, then make it read-only again
        self.configure(state="normal")
        self.delete("1.0", "end")
        if isinstance(text, list):
            for item in text:
                self.insert("end", item + "\n")
        elif isinstance(text, str):
            self.insert("end", text + "\n")
        self.configure(state="disabled")

    def append_text(self, text):
        '''
        Append text to the text display widget without clearing it
        '''
        self.configure(state="normal")
        self.insert("end", text)
        self.yview("end")
        self.configure(state="disabled")
