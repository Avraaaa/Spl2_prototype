# FastAPI ML-specific instructions
Use Python only for the FastAPI/Sentence-Transformers service. All installs and invocations use uv, with `--package datasoft-ml`.
Inference accepts masked text only, uses local model checkpoints, and has no database permissions or outbound AI APIs.
Return a controlled unavailable response if a model is not provisioned; do not weaken main portal availability.
Don't preload or download model weights during basic smoke tests.
