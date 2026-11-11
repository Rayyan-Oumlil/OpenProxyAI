---
title: Evaluating changes
description: Test a model or a prompt against real examples in the console before you ship it.
---

# Evaluating changes

The **Evaluate** group in the sidebar is where you find out whether a change is better before your users do. Everything here is for admins. The same things are available through the API: see [Datasets](/api-reference/datasets), [Evaluators and eval runs](/api-reference/eval-runs), [Feedback](/api-reference/feedback) and the guides on [capturing traffic](/guides/payload-capture), [adaptive experiments](/guides/adaptive-experiments) and [promoting prompts](/guides/prompt-promotion).

## The loop, in the order you would use it

1. **Turn on capture** (Policy, Evaluation tab). Pick the share of delivered requests to keep. It is off until you do. Personal data is replaced before anything is stored.
2. **Collect feedback.** Your application sends thumbs or a score for answers with the request id the gateway returned.
3. **Build a dataset** (Datasets). Create one, then import captured traffic, filtered by model, date or feedback score (for example only answers people liked), or add prompts by hand with an expected answer. Rows with personal data are never imported.
4. **Create an evaluator** (Evaluators): exact match, a regular expression, or an LLM judge with criteria you write.
5. **Start a run** (Eval runs). Choose the dataset, the evaluator and the model to test. Set a cost cap. The page updates while it runs and you can cancel it.
6. **Read the result.** Open a run to see each item's answer and why it passed or failed. Items that could not be scored (refused by policy, a provider error, no expected answer) are listed separately and left out of the pass rate, not counted as failures.

## Datasets

Open a dataset to see its items, add one, import more, or delete items. An import tells you how many it copied, how many it skipped for personal data, and how many were already there. Importing the same requests twice adds nothing.

An item you write that contains personal data is refused with a reason, not quietly rewritten, because changing an expected answer would change what the test checks.

## Eval runs

A run spends real money: one model call per item, plus one per item for a judge. The cost cap stops it, and at most two runs can be active at once. The table shows cost against the cap, and a run that hit the cap is marked as stopped at the cost cap.

## Experiments

An experiment can keep a fixed traffic split, or be **adaptive**. An adaptive experiment moves traffic toward the variant people rate higher and stops by itself when one is clearly better. It needs a feedback score to judge by and a minimum number of ratings per variant (at least 20) before it decides anything.

Open **View results** to see each variant's traffic share, its chance of being the best one, and how many ratings are still needed. The winner is recorded, not switched on for you: requests keep going to the target model until you change it.

Changing the variants of a running test replaces them and the ratings collected so far stop counting. Editing only the name or settings does not.

## Prompts

On the Playground's Templates tab, a prompt marked **Draft** was edited while the promotion gate is on. Choose **Promote** to see what it still needs: a completed eval run of that exact prompt that scored enough items at the required pass rate. If it is not ready you can start that run from the dialog. An admin can override with a written reason, which is recorded in the audit log.

Turn the gate on under Policy, Evaluation.
