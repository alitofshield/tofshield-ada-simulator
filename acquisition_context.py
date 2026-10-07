"""Conservative, provenance-labelled extraction of acquisition fields."""
import re


def recorded_context(metadata, instrument_fields):
    entries = [entry for group in metadata.values() for entry in group]
    def key(text):
        return re.sub(r"[^a-z0-9]", "", str(text).lower())
    def choose(names, category=None):
        matches = []
        for entry in entries:
            path = str(entry.get('path', ''))
            if 'detectioncapability' in path.lower():
                continue
            if category and not category(entry):
                continue
            if key(entry.get('name', '')) not in names:
                continue
            value = entry.get('value')
            if isinstance(value, (str, int, float)) and str(value).strip():
                matches.append({'value': value, 'source': path + ' / ' + str(entry.get('name'))})
            elif isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value) and value:
                matches.append({'value': ', '.join(map(str, value)), 'source': path + ' / ' + str(entry.get('name'))})
        distinct = {str(m['value']) for m in matches}
        if len(distinct) == 1:
            return dict(matches[0], status='Recorded')
        return {'value': None, 'status': 'Multiple recorded values — see Parameters' if matches else 'Not recorded',
                'source': '; '.join(m['source'] for m in matches)}
    targets = lambda e: not re.search(r'environment|background|reagent|calibr|reference', str(e.get('path','')), re.I)
    return {
        'reagent': choose({'reagention', 'reagent', 'reagentmode', 'reagentionmode'}),
        'targets': choose({'targets','target','targetnames','analytes','analyte','compounds','substances','isotopes','elements'}, targets),
        'environment': choose({'environmentalmatrix','environment','samplematrix','matrix','enteredcompoundsorelements'} | {'compounds','elements'},
                              lambda e: 'environment' in str(e.get('path','')).lower() or key(e.get('name','')) in {'environmentalmatrix','environment','samplematrix','matrix'}),
        'state': choose({'instrumentstate'}),
        # Exact canonical keys include unit suffixes. Do not infer unit conversions.
        'settings': {field[1]: choose({key(field[1])}) for field in instrument_fields},
    }
