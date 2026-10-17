# Monti voice conversation test

Created: 17 October 2026. This is a manual test script, not a record of passing results.

Use the **Say** column as your spoken dialogue. Monti may use different wording;
check the expected behavior and complete audible answer rather than exact sentences.
Speak naturally in English and wait until the reply finishes before the next turn,
except in the explicit interruption tests.

## Before testing

1. Start the local stack with `rtk proxy make mvp-start`, then open
   <http://localhost:8080>.
2. Sign in with a shopper account, demo02–demo10. Read its password privately from
   `tmp/auth/credentials.txt`; do not copy passwords into this document.
3. Open **Audio settings**, enable device names, choose your microphone and output,
   then click **Test speaker**. End voice before changing devices.
4. For computer speakers, keep the default **Speaker mode on**. During Monti's reply, the mic
   is deliberately held; use **Interrupt** before speaking over a reply.
   With headphones, test **Speaker mode off** for automatic spoken interruption.
5. Click **Start voice**, grant permission, and wait for **Listening**.
6. Record the browser, device, source commit, configured Gemini model/voice and
   speaker-mode choice in the results sheet below. Do not record secrets.

Each voice session has a ten-minute limit and a one-minute idle limit. Start a
fresh session for each section below. Finish a normal sequence within ten minutes;
if the session expires, record the turn reached and continue in a fresh session.
An expected expiry is separate from an unexpected disconnect during an active turn.

## Session A — greeting, general conversation and product lookup

Keep all ten turns in the same voice session, within its time limit.

| Turn | Say | Expected behavior |
|---|---|---|
| A1 | Hello, Monti. | A complete spoken English greeting. No product lookup or invented location. |
| A2 | How can you help me today? | Explains shopping, product finding or meal suggestions conversationally. |
| A3 | What is two plus two? | Answers four aloud; the session remains available. |
| A4 | Where is the whole milk? | Finds Whole milk 1 L; speaks Aisle 2, Shelf 3; shows its card and matching route. |
| A5 | Could you repeat those directions? | Repeats the current whole-milk directions without switching products. |
| A6 | Now find jasmine rice. | Changes the selected product to Jasmine rice, Aisle 5, Shelf 1. Old milk results cannot replace it later. |
| A7 | Where do I go for toothpaste? | Finds Toothpaste, Aisle 8, Shelf 2; card, spoken location and map agree. |
| A8 | Thank you. | Gives a natural spoken acknowledgement without searching for “thank you.” |
| A9 | Where is the whole milk again? | Successfully finds whole milk again after multiple product changes. |
| A10 | Thanks, that is all for now. | Completes a spoken closing. Use **End voice** afterward and confirm capture stops. |

Fail a turn if captions appear but no audio plays, the answer cuts off unexpectedly,
or the voice pauses/disconnects before the configured session/idle limit.

## Session B — meal ideas, ingredients and clarification

Start a fresh voice session. For selection tests, use only a product Monti actually
offers; the candidate list is authoritative and may vary with catalog changes.

| Turn | Say | Expected behavior |
|---|---|---|
| B1 | Suggest a simple egg dish for dinner. | Gives a spoken meal idea. Ingredients are suggestions; no unsupported stock or shelf claims. |
| B2 | How could I make it without cheese? | Adapts the same meal idea using the preceding conversational context. |
| B3 | Where can I find eggs? | Finds Eggs 12 pack, Aisle 2, Shelf 3; shows a verified card and route. |
| B4 | And where are the onions? | Finds Onions, Aisle 1, Shelf 3. |
| B5 | Can you find milk? | Resolves the broad request using catalog results; asks for a choice when several candidates are returned. |
| B6 | I want the oat milk. | Selects a matching offered candidate or asks a further question if multiple oat milks remain. Does not invent a selection. |
| B7 | Repeat the directions to the one I selected. | Repeats the verified route for the selected product. If no selection was confirmed, asks for clarification. |
| B8 | Please find unsweetened oat milk instead. | Finds Unsweetened oat milk 1 L, Aisle 2, Shelf 2. |
| B9 | Do you have a moon-rock sandwich? | Reports no catalog match or asks a reasonable clarification; never invents a product or shelf. |
| B10 | Okay, show me bananas. | Recovers immediately with Bananas, Aisle 1, Shelf 2, in the same session. |

If B5 or B6 needs extra clarification, answer using the displayed candidate name
before moving on. Record the extra turn rather than forcing the scripted choice.

## Session C — interruption and recovery

Run each case separately so intentional disruption does not affect normal timing.

| Case | Action and dialogue | Expected behavior |
|---|---|---|
| C1: Quiet listening | Ask “Explain how to make a simple omelette.” Stay silent until the answer finishes. Then say “Where are the eggs?” | The reply finishes without hearing itself as a new request; the next request finds eggs. |
| C2: Computer speakers | Enable Speaker mode. Ask “Give me a few breakfast ideas.” During the answer click **Interrupt**, then say “Find toothpaste instead.” | Playback stops; microphone capture resumes; toothpaste is the current result. Delayed breakfast audio cannot resume. |
| C3: Headphone interruption | With headphones and Speaker mode off, ask “Explain how to make fried rice.” During the answer clearly say “Stop, where is jasmine rice?” | Detects sustained speech, stops obsolete playback and handles the new request. A brief background click should not interrupt. |
| C4: Short pause | Say “Hello,” wait about ten seconds after the reply, then ask “Where is the whole milk?” | Remains in English and answers without needing Restart voice. Do not exceed the one-minute idle limit. |
| C5: Deliberate stop | Ask “Where is chicken breast?” Click **End voice** during the reply. Start voice again and say “Hello.” | Stops capture/playback immediately; the fresh session greets without replaying old audio or directions. |
| C6: Device change | End voice, change microphone/output in Audio settings, test the output, then start and say “Can you hear me?” | Uses the new devices; replies through the chosen output. |
| C7: Selected device removed | During voice, unplug the selected external device. | Stops the affected session and shows recovery guidance. Check System default/new device, then deliberately start again. |
| C8: Logout | During a reply, click **Sign out**. Sign in again and say “Hello” in a new voice session. | Old capture/playback stops and content returns to sign-in. A fresh authenticated conversation works. |
| C9: Connection loss | In the designated test browser, go offline during a reply, then restore the connection and restart voice. Say “Find bananas.” | Shows bounded recovery, releases old audio/capture and starts a fresh session; no stale reply replaces bananas. |

For browsers without selectable audio outputs, expect **System default speaker**
and guidance to use system sound settings. Test that path separately from a
browser that supports selecting an output.

## Session D — repeated conversation within the time limit

Start a fresh session and complete the following ten prompts without refreshing or
restarting. This checks repeated turns; it does not extend the ten-minute limit.

1. “Hello.”
2. “Where is whole milk?”
3. “Repeat those directions.”
4. “Where is jasmine rice?”
5. “Repeat those directions.”
6. “Where is toothpaste?”
7. “Thank you.”
8. “Where is whole milk?”
9. “What is two plus two?”
10. “Where is jasmine rice?”

Expected: ten complete audible replies, seven grounded lookup/repeat turns, correct
current cards/routes, and no unexpected pause/disconnect. General chat does not
need to clear the previous verified card. It must not fabricate a new location.

Repeat this sequence in three fresh sessions to look for inconsistent behavior.
Keep failures in the results; restarting or repeating a failed utterance does not
turn the original attempt into a pass. These repetitions are regression checks,
not a replacement for the project's frozen performance/classifier acceptance cases.

## Bakery word-form regression

All15Bakery products are in the same catalog used by backoffice and voice. In the
backoffice, clear the status/text filter and use Next/Previous (50rows per page),
or search a product name directly. The shopper gallery lists only published items.

In one session, ask each prompt below and confirm native audio, the exact product
card, its route and the shelf shown in the gallery agree. Singular wording is
intentional; no backoffice renaming should be needed.

| Say | Expected product | Aisle / shelf |
|---|---|---|
| Where is a bagel? | Bagels | 3 / 1 |
| Where is a blueberry muffin? | Blueberry muffins | 3 / 4 |
| Find a burger bun. | Burger buns | 3 / 2 |
| Where is a cinnamon roll? | Cinnamon rolls | 3 / 1 |
| Where is a croissant? | Croissants | 3 / 4 |
| Where is chocolate cake? | Chocolate cake | 3 / 3 |

Also ask “Where is the bakery?” Expect product choices from Bakery, then select
one offered product. “Find a muffin” should clarify blueberry versus English.
“Find a gluten-free muffin” must not claim that unsupported modifier matches.

## Product reference for the seeded catalog

These values come from `data/demo-store.json` and `data/catalog-expansion-v2.json`.
If backoffice edits have changed a product, verify the current published catalog
before using these locations as the test expectation. Do not infer shelf height,
bay number, prices or stock availability from the illustration.

| Product | Product ID | Aisle | Shelf |
|---|---|---|---|
| Whole milk 1 L | milk-whole-1l | 2 | 3 |
| Unsweetened oat milk 1 L | unsweetened-oat-milk-1l | 2 | 2 |
| Eggs 12 pack | eggs-12-pack | 2 | 3 |
| Onions | onions | 1 | 3 |
| Jasmine rice | jasmine-rice | 5 | 1 |
| Toothpaste | toothpaste | 8 | 2 |
| Bananas | bananas | 1 | 2 |
| Chicken breast | chicken-breast | 4 | 1 |

## Results sheet

Copy this section for each run. Record synthetic test outcomes and safe error codes;
do not include passwords, cookie values, provider keys or real shopper recordings.

- Date/time/timezone:
- Tester:
- Source commit / serving revision:
- URL:
- Browser / version:
- Computer / operating system:
- Microphone / output device:
- Speaker mode: on / off
- Configured Gemini model / voice:
- Scenario / run number:

| Turn/case | Reply started after speech ended (ms) | Full audible reply? | Correct card/location? | Voice status / safe error code | PASS / FAIL / BLOCKED / NOT RUN |
|---|---|---|---|---|---|
| | | | | | |

For a failure also record whether captions appeared, whether playback stopped
mid-sentence, whether the microphone remained on, and the last successfully
completed turn. Measure from the end of your utterance to the first audible reply;
record verified-card time separately for shopping requests. Do not treat a general
“let me check” filler as the first actionable shopping answer.

The broader release targets are warm p95 ≤5 seconds to first actionable speech and
≤8 seconds to a verified card across the required 30 measured trials. Manual
stopwatch observations here are useful diagnosis, not proof that those gates pass.

Related procedures: [readiness runbook](sdlc/09-operations/READINESS.md),
[authentication/device acceptance](sdlc/07-tests/TEST-0013.md), and
[general-conversation diagnosis](VOICE-CONVERSATION-FIX-2026-10-16.md).
