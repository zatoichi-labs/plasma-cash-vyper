import vyper


def get_interface(contract_filename):
    with open(contract_filename, 'r') as f:
        interface = vyper.compile_code(
                f.read(),
                output_formats=['abi', 'bytecode', 'bytecode_runtime']
            )
    return interface


token_interface = get_interface('contracts/Token.vy')
rootchain_interface = get_interface('contracts/RootChain.vy')
