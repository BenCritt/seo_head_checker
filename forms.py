class SitemapForm(forms.Form):
    """
    A Django form for collecting sitemap URLs and file type preferences for the SEO Head Checker tool.

    Fields:
        sitemap_url (str): The URL of the sitemap to process. Must be a valid URL.
        file_type (str): The preferred output file format, either Excel or CSV.
    """

    sitemap_url = forms.CharField(
        # Label displayed on the form with SEO-friendly lanaguage.
        label="Enter Sitemap URL",
        # Make this field mandatory.
        required=True,
        # Provide a placeholder so the expected input is made clear to the user.
        widget=forms.TextInput(
            attrs={
                "name": "sitemap_url",
                "id": "sitemap_url",
                "placeholder": "bencritt.net/sitemap.xml",
            }
        ),
    )

    def clean_sitemap_url(self):
        """
        Cleans and validates the 'sitemap_url' field submitted in the form.

        - Strips leading and trailing whitespace from the input URL.
        - Normalizes the URL (e.g., ensures it starts with 'http://' or 'https://').
        - Raises a validation error if the URL is invalid or cannot be normalized.

        Returns:
            str: The normalized URL if valid.

        Raises:
            forms.ValidationError: If the URL is invalid.
        """
        # Get the user-submitted URL and strip any whitespace
        url = self.cleaned_data["sitemap_url"].strip()
        try:
            # Normalize the URL (ensures it starts with http:// or https://)
            return normalize_url(url)
        except Exception:
            # Raise a validation error if the URL is invalid
            raise forms.ValidationError("Please enter a valid sitemap URL.")
