def validation_issues(collection, obs, commands, manifest):
    issues = []
    if (collection.get('reviewed_stage_digest') != scope.STAGE_DIGEST or
            manifest.get('context_sha256') != scope.CONTEXT_SHA or
            not collection.get('identity_verified') or not collection.get('input_hashes_verified')):
        issues.append('reviewed device/stage/context binding not established')
    if collection.get('error') or collection.get('process_timeout') or collection.get('process_exit_code') != 0:
        issues.append('controller reported an error, timeout or nonzero/unknown process exit')
    if not obs.get('query_completion_observed_beyond_exit_code'):
        issues.append('query/HTP completion with nonempty UTF8 output not established')
    prompt = obs.get('prompt', {})
    if not prompt.get('rendered_bytes_exact_in_runtime_stdout') or not prompt.get('single_bos_prefix_observed'):
        issues.append('runtime rendered bytes or single-BOS prefix not established')
    if any(not item['matches_bound_prefix'] for item in prompt.get('runtime_prefix_observations', [])):
        issues.append('logged token prefix differs from frozen input')
    if prompt.get('profile_prompt_tokens') not in (None, 1929):
        issues.append('runtime prompt count differs from1929')
    if obs.get('stop', {}).get('configured_ceiling_observed') != 2048:
        issues.append('requested max2048 setting not observed')
    generated = obs.get('actual_generated_tokens')
    if generated is not None and not 0 < generated <= 2048:
        issues.append('generated count outside the long ceiling')
    for name in ('graph_execute_nonzero_status', 'cpu_backend_markers', 'runtime_fallback_markers', 'cache_quantization_error'):
        if obs.get('execution_markers', {}).get(name):
            issues.append('route/execution marker requires review: '+name)
    operations = [c.get('operation') for c in commands]
    ordered = ('raw.pull' in operations and 'cleanup.remove' in operations and
               operations.index('raw.pull') < operations.index('cleanup.remove'))
    if not (collection.get('raw_pull_completed') and collection.get('cleanup') == 'verified_absent' and
            collection.get('process_cleanup', {}).get('all_absent') and collection.get('phone_lock_released') and ordered):
        issues.append('capture/cleanup lifecycle incomplete')
    if not commands or not all(c.get('lock_held') and c.get('lock_fd_inheritable') is False for c in commands):
        issues.append('full noninherited phone-lock coverage not established')
    return issues
