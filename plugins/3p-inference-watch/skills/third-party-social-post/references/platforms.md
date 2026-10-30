# Platform shapes

## LinkedIn

**Length:** 120–200 words. Past roughly 200 the post truncates behind "see more" and the
close is lost.

**Shape:**

1. **First line is the whole hook.** It appears in the feed alone. Make it a specific claim,
   not a tease. "One bad marketplace entry used to take down every plugin on the device" beats
   "Interesting change in this week's Claude Desktop release."
2. Two or three sentences of substance — what changed, what condition it applies under, what
   an administrator should do.
3. One closing line. A question only if it is a real one worth answering.
4. Source link on its own line at the end.

**Formatting:** Plain paragraphs with line breaks between them. No markdown — LinkedIn renders
none of it, so `**bold**` shows up as literal asterisks. Backticks around configuration keys
are the one exception worth keeping despite this; they read as intentional and the alternative
is worse. At most one short list, three items maximum. No emoji by default.

**Do not:** open with "🚨", "Big news", "PSA", or "Let's talk about". Do not end with "Thoughts?"
or a stack of hashtags. Two hashtags maximum, at the very end, only if they are real terms
people follow.

## X

**Single post:** 280 characters. One claim, the version number, and a link. If the point does
not survive compression to one claim, it is a thread or it is nothing.

**Thread:** three to five posts, never padded to reach a number.

- Post 1: the claim, standing alone. It must be worth reading even if nobody expands the
  thread.
- Posts 2–4: the mechanism, the condition, the action. One idea each.
- Final post: the source link.

**Formatting:** No thread numbering ("1/5") unless the thread exceeds four posts. No emoji.
Line breaks within a post are fine and improve readability. Configuration keys in plain text —
backticks render as literal characters.

**Do not:** write a hook post that withholds the point. "A change shipped this week that
affects every 3P deployment 🧵" is the pattern to avoid entirely.

## Internal chat (Slack, Teams)

Only when the user explicitly asks for an internal version. This is the one output where the
brief's **Relevance to our deployment** section may be used, because it is not publication.

**Shape:** Two to four sentences, lead with the action item, name the release version, link the
brief file rather than pasting it. Mention specific people only if the user named them.

Keep this output in a separate file from the public drafts so the two never get confused:
`social/YYYY-MM-DD-internal.md`.
