import os, sys
sys.path.insert(0, "/tmp/nt-remote/backend")
from app import llm
from app.main import create_app
import uvicorn

class Scripted:
    provider, model = "fake", "fake-stt"
    def transcribe(self, audio, mime, language):
        try:
            lines = open("/tmp/stt_lines.txt").read().splitlines()
        except FileNotFoundError:
            lines = []
        text = lines.pop(0) if lines else ""
        open("/tmp/stt_lines.txt", "w").write("\n".join(lines))
        open("/tmp/stt_calls.log", "a").write(f"{len(audio)} {mime} {language}\n")
        return llm.Reply(text, self.provider, self.model)

app = create_app()
app.state.get_stt = lambda: Scripted()
uvicorn.run(app, port=8000, access_log=False)
