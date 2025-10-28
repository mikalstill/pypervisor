import ctypes

from prettytable import PrettyTable


def pretty_print_struct(s, ignore_fields=[]):
    # This relies on the magic of ctypes.Structure.
    table = PrettyTable()
    table.field_names = ['Name', 'Type', 'Value']
    table.align = 'l'

    for field_name, field_type in s._fields_:
        if field_name.startswith('_'):
            continue
        if field_name in ignore_fields:
            continue

        size = ctypes.sizeof(field_type)
        row = [
            field_name,
            f'{field_type.__name__} ({size} bytes)'
        ]

        value = getattr(s, field_name)
        if isinstance(value, int):
            row.append(f'      0x{value:x} ({value})')
        elif hasattr(field_type, '_length_'):
            array = []
            for i, item in enumerate(value):
                array.append(f'[{i:2}]: 0x{item:x} ({item})')
            row.append('\n'.join(array))
        elif hasattr(field_type, '_fields_'):
            row.append(pretty_print_struct(value))
        else:
            row.append(f'      {value}')

        table.add_row(row)

    return table.get_string()


def pretty_print_sregs(s):
    out = ''

    out += 'Segment registers:\n'
    table = PrettyTable()
    table.align = 'l'

    field_names = ['Name']
    field_types = ['']
    rows = []

    for register_name in ['cs', 'ds', 'es', 'fs', 'gs', 'ss', 'tr', 'ldt']:
        reg_s = getattr(s, register_name)
        row = [register_name]
        for field_name, field_type in reg_s._fields_:
            if register_name == 'cs':
                field_names.append(field_name)
                field_types.append(field_type.__name__)
            value = getattr(reg_s, field_name)
            row.append(f'0x{value:x} ({value})')
        rows.append(row)

    table.field_names = field_names
    table.add_row(field_types)
    for row in rows:
        table.add_row(row)
    out += table.get_string()
    out += '\n\n'

    out += 'Descriptor tables:\n'
    table = PrettyTable()
    table.align = 'l'

    field_names = ['Name']
    field_types = ['']
    rows = []

    for dtable_name in ['gdt', 'idt']:
        reg_s = getattr(s, dtable_name)
        row = [dtable_name]
        for field_name, field_type in reg_s._fields_:
            if dtable_name == 'gdt':
                field_names.append(field_name)
                field_types.append(field_type.__name__)
            value = getattr(reg_s, field_name)
            if hasattr(field_type, '_length_'):
                array = []
                for i, item in enumerate(value):
                    array.append(f'[{i:2}]: 0x{item:x} ({item})')
                row.append('\n'.join(array))
            else:
                row.append(f'0x{value:x} ({value})')
        rows.append(row)

    table.field_names = field_names
    table.add_row(field_types)
    for row in rows:
        table.add_row(row)
    out += table.get_string()
    out += '\n\n'

    out += 'The other bits:\n'
    out += pretty_print_struct(
        s,
        ignore_fields=[
            'cs', 'ds', 'es', 'fs', 'gs', 'ss', 'tr', 'ldt', 'gdt', 'idt'
        ])

    return out
