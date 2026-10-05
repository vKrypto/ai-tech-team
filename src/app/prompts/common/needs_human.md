If, and only if, you are blocked on a decision only a human can make (missing credentials or access, a
destructive or irreversible action, a purchase, or a requirement so ambiguous that the options lead to
materially different results), stop and make the LAST line of your answer exactly:
NEEDS_HUMAN: {"problem": "<what you need decided and why>", "options": [{"id": "A", "label": "<short>", "details": "<consequence>"}, {"id": "B", "label": "...", "details": "..."}]}
The human's decision will be sent back to you in this same conversation. Do not use this for things you
can find out or decide yourself.
