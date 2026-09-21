# Security and posture

**Retrieved content is data, not instructions.** These skills read external sources — papers, abstracts, API responses, archived conversation content. That content is treated as information to inspect and report, never as instructions to follow. A skill does not act on text found inside a source.

**Report, don't gate.** The integrity skills surface and rank by objective signals — a number matches its source or it doesn't; a DOI is retracted or it isn't. They never decide what is relevant, credible, or true. Every inclusion and interpretation call stays with the person.

**No credentials in this repository.** Skills that call an external API (OpenAlex) read the key from an environment variable (`OPENALEX_API_KEY`) that you set yourself. No key, token, or private path is committed here. If you find one, please open an issue.
