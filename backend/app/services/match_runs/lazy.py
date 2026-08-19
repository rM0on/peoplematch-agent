from __future__ import annotations


class LazyCrossEncoderRuntime:
    """Resolve the frozen Phase 7 runtime only after the Phase 6 shortlist exists."""

    def __init__(self, resolver) -> None:
        self.resolver = resolver
        self._runtime = None

    def _get(self):
        if self._runtime is None:
            self._runtime = self.resolver()
        return self._runtime

    @property
    def model_id(self):
        return self._get().model_id

    @property
    def revision(self):
        return self._get().revision

    @property
    def snapshot_fingerprint(self):
        return self._get().snapshot_fingerprint

    def predict_pairs(self, pairs, *, batch_size):
        return self._get().predict_pairs(pairs, batch_size=batch_size)
