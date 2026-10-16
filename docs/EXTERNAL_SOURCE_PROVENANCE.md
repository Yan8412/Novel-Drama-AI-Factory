# Method references and license review

The following files and licenses were retrieved from their primary repositories
at the pinned revisions during this review. No upstream implementation, prompt
text, model weights, or runtime dependency is vendored. Concepts were adapted into
independently written standard-library checks and synthetic tests.

| Source | Pinned revision | Reviewed license | Narrow method and limitation |
|---|---|---|---|
| [LTX-Video](https://github.com/Lightricks/LTX-Video) | `4b2d053057623ddd4d0a1d3e9cd28890e9ef487f` | [Apache-2.0](https://github.com/Lightricks/LTX-Video/blob/4b2d053057623ddd4d0a1d3e9cd28890e9ef487f/LICENSE) | Chronological observable action and camera description; its enhancer returns original prompts for multiple conditioning items or a nonzero initial conditioning frame. |
| [VideoGen-of-Thought](https://github.com/WenjieShu/VideoGen-of-Thought) | `5bfe9723b5597391f093ec3848d751486fdb1692` | [BSD-3-Clause](https://github.com/WenjieShu/VideoGen-of-Thought/blob/5bfe9723b5597391f093ec3848d751486fdb1692/LICENSE) | Structured character/background/relation/camera/lighting completeness; text similarity and completeness do not establish contact mechanics. |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | `6e0991ccab72a9f376782b44c551b7ded47738f5` | [MIT](https://github.com/promptfoo/promptfoo/blob/6e0991ccab72a9f376782b44c551b7ded47738f5/LICENSE) | Candidate comparison and negative regression cases; actual optimizer calls a provider, so it is not invoked here. |

Inspected implementation locations:

- LTX-Video `ltx_video/utils/prompt_enhance_utils.py`, especially conditioning handling at lines 75-87.
- VideoGen-of-Thought `scripts/dynamic_storyline_system.py`, completeness and validation at lines 34-62.
- Promptfoo `src/optimizer/promptOptimizer.ts`, suggestions-provider call at lines 214-215.

The supplied candidate archive is user-provided code, modified for this isolated
review. No third-party snippet has been pasted into it during integration. Its
own repository license has not been selected by the owner; publication alone is
not an open-source license grant. This is an outstanding distribution choice,
not an assertion that upstream licenses cover this independently authored code.
Future code copying or dependency adoption requires its own attribution and
license review, including model weights and transitive dependencies.

GitHub Actions references are pinned to inspected full Git commit IDs. No workflow
was dispatched. Hosted images and runtimes may evolve and require a fresh review
before a separately authorized run.
