# Feature: voice summary

The therapist records a voice memo on their phone right after a session. The app uploads
the audio, a speech-to-text API transcribes it, and an LLM API turns the transcript into a
one-page summary emailed to the client's parents.

- Input: audio (1 to 5 minutes), the client's first name, age and the therapist's notes.
- Storage: audio and transcript kept in the app's object storage bucket; the summary in SQLite.
- Providers: a US-based speech-to-text API and a US-based LLM API, both called from the backend.
- Recipients: the parents' email address on file.
- Retention: not decided.
