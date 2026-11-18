# Tasks

## 1. Slack Web API client wiring

- [x] 1.1 Add `slack-sdk` as a direct, pinned dependency in
      `requirements.txt` (matching the version already installed
      transitively via `slack-bolt`, confirmed `3.44.1`) and verify
      `pip install -r requirements.txt` succeeds with no version
      conflict.
- [x] 1.2 Create `src/integrations/slack_notify.py` with
      `build_client(bot_token: str) -> WebClient`, `set_client()`,
      `get_client()` (mirroring `src/integrations/keycloak.py`'s
      pattern exactly), plus `set_default_channel(channel_id: str)` /
      `get_default_channel() -> str` module-level singletons for the
      channel-defaulting mechanism settled in design.md. Verify with a
      unit test that `get_client()`/`get_default_channel()` raise
      clearly before `set_*()` is called, and return the installed
      value after.
- [x] 1.3 Wire both into `src/main.py` at startup, next to the existing
      Keycloak/Discourse client setup: `build_client(os.environ
      ["SLACK_BOT_TOKEN"])` → `set_client()`, and
      `set_default_channel(config.slack.trusted_channel_id)`. Verify by
      starting the service locally (or via the existing test suite's
      app-construction tests) and confirming no startup error.

## 2. `slack_notify` action executor

- [x] 2.1 Create `src/actions/slack_notify.py` implementing `notify(action:
      Action, event: TriggerEvent, dry_run: bool = False) -> ActionResult`:
      render `action.message` via `string.Template(action.message)
      .substitute(openmrs_id=event.openmrs_id)`; resolve the destination
      channel as `action.channel or slack_notify_integration
      .get_default_channel()`. Verify with a unit test that a template
      with `${openmrs_id}` renders correctly and that an explicit
      `channel` overrides the default.
- [x] 2.2 Handle the `KeyError` from an unrecognized template placeholder
      by returning `ActionResult(status="failure", detail="Unknown
      template placeholder: ...")` without calling the Slack API.
      Verify with a unit test using a template referencing an unknown
      placeholder (e.g. `${bogus}`).
- [x] 2.3 Implement the dry-run path: when `dry_run` is `True`, render
      the message and return `ActionResult(status="dry_run", detail=
      f"Would post to {channel}: {rendered}")` without calling
      `chat_postMessage`. Verify with a unit test asserting the mocked
      Slack client's `chat_postMessage` is never called when `dry_run=True`.
- [x] 2.4 Implement the real-post path: call
      `get_client().chat_postMessage(channel=channel, text=rendered)`
      and return `ActionResult(status="success", detail=..., action_detail=...)`
      on success. Verify with a unit test using a mocked client asserting
      the call arguments and the returned `ActionResult`.
- [x] 2.5 Implement Slack API failure handling: catch
      `slack_sdk.errors.SlackApiError`, return
      `ActionResult(status="failure", detail=...)` always, and when
      `exc.response["error"]` is one of `missing_scope`, `not_in_channel`,
      `channel_not_found`, log the troubleshooting hint from proposal.md
      naming the destination channel; for any other error code, log the
      raw error with no hint. Verify with unit tests for both branches
      (one of the three hinted codes, and an unrelated code), asserting
      on captured log output.
- [x] 2.6 Register the new action type in `src/actions/__init__.py`'s
      `register_all()`: `register_action("slack_notify", slack_notify
      .notify)`. Verify with a unit test (mirroring
      `tests/unit/integrations/test_slack.py`'s registry-lookup style)
      that `ACTION_EXECUTORS["slack_notify"]` resolves to this function
      after `register_all()` runs.

## 3. End-to-end rule evaluation

- [x] 3.1 Add an integration test exercising `evaluator.evaluate()` +
      `evaluator.execute_rule()` for a rule with two actions
      (`keycloak_add_groups` then `slack_notify`) against a real
      `TriggerEvent`, with both clients mocked, verifying: both actions
      run, both results are recorded as separate `audit_log` rows via
      `record_event()`, and a `slack_notify` failure does not prevent
      the `keycloak_add_groups` result from being recorded (per
      `execute_rule()`'s existing per-action isolation).

## 4. Example config and documentation

- [x] 4.1 Add `slack_notify` as a second action on the "Grant community
      edit access (Discourse TL2)" and "Revoke community edit access
      (Discourse TL drop)" rules in `config/rules.example.yaml`, with
      `message: "${openmrs_id} trusted by OpenMRS Talk"` / `"${openmrs_id}
      no longer trusted by OpenMRS Talk"`, and comments documenting the
      optional `channel` field (ID or `#name`, defaulting to
      `slack.trusted_channel_id`) and the `${openmrs_id}` placeholder.
      Verify `openspec/specs/config-schema.md` is reachable from the spec
      (it already is) and that the example YAML is still valid by
      loading it through `src/engine/loader.py`'s `RuleSet.model_validate()`
      in a quick unit test.
- [x] 4.2 Update `openspec/specs/config-schema.md`'s embedded `rules.yaml`
      example to match 4.1's addition to the Discourse-TL2 grant rule,
      and add a new `### slack_notify action: optional channel, templated
      message` subsection under "Notes & Design Decisions" documenting
      the channel-defaulting and interpolation behavior, matching the
      style of the existing "Webhook and Workflow triggers" subsection.
      Verify by reading the rendered section for consistency with the
      YAML example above it.

- [x] 4.3 Document the `chat:write` OAuth scope requirement (alongside
      the existing `commands` scope needed for slash commands) in
      README.md's "Set up Slack" section. Verified by reading the
      updated section for consistency with the rest of its setup steps.

## 5. Full-suite verification

- [x] 5.1 Run the full test suite (`pytest`) and confirm it passes,
      including all new unit/integration tests from groups 1-3 and the
      existing suite unaffected by this change.

## Workflow follow-up

- Deploy with `rules.yaml` still unchanged (the new action type exists
  but isn't referenced by any live rule yet), then add `slack_notify` to
  the two Discourse-triggered rules in the live `/config/rules.yaml` and
  confirm live, against the real Slack workspace, that a Discourse
  trust-level change posts the expected message to the trusted channel.
- Confirm live that a deliberately-misconfigured `channel` (one trustbot
  is not a member of) produces the troubleshooting-hint log line.
- Archive this change once implementation and live verification are
  complete.
- Consider releasing as a minor version, consistent with how
  `/trust-activity` and Slack in-channel visibility were released.
