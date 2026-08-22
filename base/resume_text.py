import pymupdf

class ResumeText:
    def extract_text(resume):
        if isinstance(resume, (bytes, bytearray)):
            doc = pymupdf.open(stream=resume, filetype="pdf")
        else:
            doc = pymupdf.open(resume)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
