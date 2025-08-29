import pytest
from ape.exceptions import ContractLogicError


@pytest.mark.parametrize("num_modules", [1, 2, 3])
def test_add_module(safe, create_module, num_modules):
    for _ in range(num_modules):
        module = create_module()

        assert module not in safe.modules
        receipt = safe.modules.enable(module)

        assert module in safe.modules
        assert receipt.events == [
            safe.contract.EnabledModule(module),
            safe.contract.ExecutionSuccess(),
        ]


@pytest.mark.parametrize("num_modules", [1, 2, 3])
def test_remove_module(safe, create_module, num_modules):
    for _ in range(num_modules):
        module = create_module()

        safe.modules.enable(module)
        assert module in safe.modules

    for module in safe.modules:
        receipt = safe.modules.disable(module)
        assert module not in safe.modules
        assert receipt.events == [
            safe.contract.DisabledModule(module),
            safe.contract.ExecutionSuccess(),
        ]


def test_module_works(safe, create_module, deployer):
    module = create_module()
    with pytest.raises(ContractLogicError, match="GS104"):
        module.test(safe, sender=deployer)

    safe.modules.enable(module)
    assert module in safe.modules

    module.test(safe, sender=deployer)
