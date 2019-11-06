from pathlib import Path as _Path

import vyper as _vyper


def _get_interface(contract_filename):
    base_path = _Path(__file__).parent
    full_path = (base_path / '..' / contract_filename).resolve()
    with open(full_path, 'r') as f:
        interface = _vyper.compile_code(
                f.read(),
                output_formats=['abi', 'bytecode', 'bytecode_runtime']
            )
    return interface


token_interface = _get_interface('contracts/Token.vy')
rootchain_interface = _get_interface('contracts/RootChain.vy')
