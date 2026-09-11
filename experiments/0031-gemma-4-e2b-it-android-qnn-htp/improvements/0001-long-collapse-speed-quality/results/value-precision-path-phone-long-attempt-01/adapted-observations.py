def observations(raw, command_root):
    device = raw / 'raw/device'
    log = (device / 'genie-verbose.log').read_text(errors='replace')
    stdout = (device / 'runner.stdout').read_bytes()
    output_path = device / 'long-output.txt'
    output_bytes = output_path.read_bytes()
    output = output_bytes.decode('utf-8')
    events, profile_error = profile_events(device / 'long-profile.json')
    creates = [event for event in events if event.get('type') == 'GenieDialog_create']
    queries = [event for event in events if event.get('type') == 'GenieDialog_query']
    query = queries[-1] if queries else {}
    def value(key):
        return query.get(key, {}).get('value')
    markers = {
        'context_deserialized': 'Context 1 deserialized on pd 0',
        'two_graphs_initialized': 'qnn-api initialized with 2 graph(s)',
        'physical_soc_detected': 'Detected Snapdragon SOC SM8550',
        'htp_initialized': 'HTP: initialization completed successfully',
        'stub_connection': 'First connection to QNN stub established',
        'weight_sharing': 'prepared with Weight Sharing enabled',
        'graph_execute_started': 'QnnGraph_execute started',
        'graph_execute_status0': 'QnnGraph_execute done. status 0x0',
        'ar128_completed_status0': 'Graph ar128_cl4096_1_of_1 execution finished with result 0',
        'ar1_completed_status0': 'Graph ar1_cl4096_1_of_1 execution finished with result 0',
        'dialog_create_enter': 'Entering GenieDialog_create',
        'dialog_create_return': 'Returning from GenieDialog_create',
        'query_enter': 'Entering GenieDialog_query', 'query_return': 'Returning from GenieDialog_query',
        'dialog_free_return': 'Returning from GenieDialog_free',
        'smart_mask_selected': 'Initializing with KV$ update method = SMART_MASK',
        'cache_quantization_error': 'Non-identical quantization parameters',
        'known_cross_attention_warning': 'qnn-htp-engine does not support usesCrossAttention',
    }
    counts = {key: log.count(marker) for key, marker in markers.items()}
    counts['cpu_backend_markers'] = len(re.findall(r'QnnCpu|CPU backend', log, re.I))
    counts['runtime_fallback_markers'] = len(re.findall(r'fallback', log, re.I))
    statuses = re.findall(r'QnnGraph_execute done\. status (\S+)', log)
    counts['graph_execute_nonzero_status'] = sum(status != '0x0' for status in statuses)
    expected_prompt = (FROZEN / 'prompts/long.txt').read_bytes()
    token_data = (FROZEN / 'token-ids/long.int32le').read_bytes()
    tokens = list(struct.unpack('<1929i', token_data))
    start = stdout.find(b'[PROMPT]: ')
    prompt_exact = start >= 0 and stdout[start + 10:start + 10 + len(expected_prompt)] == expected_prompt
    prefixes = []
    for line in log.splitlines():
        if 'embedding-tokens:' not in line:
            continue
        tail = line.split('embedding-tokens:', 1)[1].strip()
        complete = [int(item) for item in re.findall(r'(-?\d+)\s*(?=[,\]])', tail)]
        fragment = re.search(r',\s*(\d+)$', tail) if not tail.endswith(']') else None
        prefixes.append({'complete_token_count': len(complete), 'complete_prefix': complete,
                         'matches_bound_prefix': complete == tokens[:len(complete)],
                         'logger_truncated': not tail.endswith(']'),
                         'last_numeric_fragment': fragment[1] if fragment else None})
    caps = re.findall(r'^> dialog setMaxNumTokens dialog1 (\d+)$', stdout.decode(), re.M)
    complete_query = (counts['query_enter'] == 1 and counts['query_return'] == 1
                      and counts['graph_execute_status0'] > 0 and bool(output.strip()))
    return {
        'query_completion_observed_beyond_exit_code': complete_query,
        'execution_markers': counts,
        'prompt': {'rendered_bytes_exact_in_runtime_stdout': prompt_exact,
                   'rendered_sha256': sha(FROZEN / 'prompts/long.txt'),
                   'token_ids_sha256': sha(FROZEN / 'token-ids/long.int32le'),
                   'expected_tokens': 1929, 'profile_prompt_tokens': value('num-prompt-tokens'),
                   'runtime_prefix_observations': prefixes, 'bos_config': -1,
                   'single_bos_prefix_observed': bool(prefixes) and all(p['complete_prefix'][:2] == [2, 105] for p in prefixes)},
        'output': {'path': 'raw/controller/raw/device/long-output.txt', 'bytes': len(output_bytes), 'sha256': sha(output_path)},
        'actual_generated_tokens': value('num-generated-tokens'),
        'stop': {'configured_ceiling_observed': int(caps[-1]) if caps else None,
                 'ceiling_reached': (value('num-generated-tokens') == 2048 and caps == ['2048']
                                     if value('num-generated-tokens') is not None and caps else None),
                 'query_returned_normally': counts['query_return'] == 1,
                 'explicit_runtime_stop_reason': None,
                 'missing_reason': 'No independent EOS-versus-limit stop enum/event is exposed in the retained profile/log. Configured max2048 was set and reached; do not invent an EOS event.'},
        'raw_genie_profile': {'create_event': creates[-1] if creates else None, 'query_event': query or None,
                              'profile_error': profile_error,
                              'normalized_decode_tokens_per_second': None,
                              'normalized_decode_missing_reason': 'Genie does not define first-token inclusion for its rate; raw rate is not a normalized comparison metric.',
                              'scope': 'One max2048 engineering observation; runtime-defined timing boundaries, no speed acceptance or campaign distribution.'},
    }
