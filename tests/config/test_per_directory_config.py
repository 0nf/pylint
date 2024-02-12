# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import os
import os.path
from pathlib import Path

import pytest
from pytest import CaptureFixture

from pylint.lint import Run as LintRun
from pylint.testutils._run import _Run as Run


def test_fall_back_on_base_config(tmp_path: Path) -> None:
    """Test that we correctly fall back on the base config."""
    # A file under the current dir should fall back to the highest level
    # For pylint this is ./pylintrc
    test_file = tmp_path / "test.py"
    runner = Run([__name__], exit=False)
    assert id(runner.linter.config) == id(runner.linter._base_config)

    # When the file is a directory that does not have any of its parents in
    # linter._directory_namespaces it should default to the base config
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("1")
    Run([str(test_file)], exit=False)
    assert id(runner.linter.config) == id(runner.linter._base_config)


@pytest.fixture
def _create_subconfig_test_fs(tmp_path: Path) -> tuple[Path, ...]:
    level1_dir = tmp_path / "level1_dir"
    level1_init = level1_dir / "__init__.py"
    conf_file1 = level1_dir / "pylintrc"
    test_file1 = level1_dir / "a.py"
    test_file3 = level1_dir / "z.py"
    level1_dir_without_config = tmp_path / "level1_dir_without_config"
    level1_init2 = level1_dir_without_config / "__init__.py"
    test_file4 = level1_dir_without_config / "aa.py"
    subdir = level1_dir / "sub"
    level2_init = subdir / "__init__.py"
    conf_file2 = subdir / "pylintrc"
    test_file2 = subdir / "b.py"
    os.makedirs(level1_dir_without_config)
    os.makedirs(subdir)
    level1_init.touch()
    level1_init2.touch()
    level2_init.touch()
    test_file_text = "#LEVEL1\n#LEVEL2\n#ALL_LEVELS\n#TODO\n"
    test_file1.write_text(test_file_text)
    test_file2.write_text(test_file_text)
    test_file3.write_text(test_file_text)
    test_file4.write_text(test_file_text)
    conf1 = "[MISCELLANEOUS]\nnotes=LEVEL1,ALL_LEVELS"
    conf2 = "[MISCELLANEOUS]\nnotes=LEVEL2,ALL_LEVELS"
    conf_file1.write_text(conf1)
    conf_file2.write_text(conf2)
    return level1_dir, test_file1, test_file2, test_file3, test_file4


@pytest.mark.parametrize(
    "local_config_args",
    [["--use-local-configs=y"]],
)
# check modules and use of configuration files from top-level package or subpackage
@pytest.mark.parametrize("test_file_index", [0, 1, 2])
# check cases when cwd contains pylintrc or not
@pytest.mark.parametrize(
    "start_dir_modificator", [".", "..", "../level1_dir_without_config"]
)
def test_subconfig_vs_root_config(
    _create_subconfig_test_fs: tuple[Path, ...],
    capsys: CaptureFixture,
    test_file_index: int,
    local_config_args: list[str],
    start_dir_modificator: str,
) -> None:
    """Test that each checked file or module uses config
    from its own directory.
    """
    level1_dir, *tmp_files = _create_subconfig_test_fs
    test_file = tmp_files[test_file_index]
    start_dir = (level1_dir / start_dir_modificator).resolve()

    orig_cwd = os.getcwd()
    output = [f"{start_dir = }, {test_file = }"]
    os.chdir(start_dir)
    for _ in range(2):
        # _Run adds --rcfile, which overrides config from cwd, so we need original Run here
        LintRun([*local_config_args, str(test_file)], exit=False)
        output.append(capsys.readouterr().out.replace("\\n", "\n"))

        test_file = test_file.parent
    os.chdir(orig_cwd)

    expected_note = "LEVEL1"
    if test_file_index == 1:
        expected_note = "LEVEL2"
    assert_message = f"Wrong note after checking FILE. Readable debug output:\n{output[0]}\n{output[1]}"
    assert expected_note in output[1], assert_message
    assert_message = f"Wrong note after checking DIRECTORY. Readable debug output:\n{output[0]}\n{output[2]}"
    assert expected_note in output[2], assert_message

    if test_file_index == 0:
        # 'pylint level1_dir/' should use config from subpackage when checking level1_dir/sub/b.py
        assert_message = f"Wrong note after checking DIRECTORY. Readable debug output:\n{output[0]}\n{output[2]}"
        assert "LEVEL2" in output[2], assert_message
    if test_file_index == 1:
        # 'pylint level1_dir/sub/b.py' and 'pylint level1_dir/sub/' should use
        # level1_dir/sub/pylintrc, not level1_dir/pylintrc
        assert_message = f"Wrong note after checking FILE. Readable debug output:\n{output[0]}\n{output[1]}"
        assert "LEVEL1" not in output[1], assert_message
        assert_message = f"Wrong note after checking DIRECTORY. Readable debug output:\n{output[0]}\n{output[2]}"
        assert "LEVEL1" not in output[2], assert_message


@pytest.mark.parametrize(
    "local_config_args",
    [["--use-local-configs=y"]],
)
# check cases when test_file without local config belongs to cwd subtree or not
@pytest.mark.parametrize(
    "start_dir_modificator", [".", "..", "../level1_dir_without_config"]
)
def test_missing_local_config(
    _create_subconfig_test_fs: tuple[Path, ...],
    capsys: CaptureFixture,
    local_config_args: list[str],
    start_dir_modificator: str,
) -> None:
    """Test that when checked file or module doesn't have config
    in its own directory, it uses default config or config from cwd.
    """
    level1_dir, *tmp_files = _create_subconfig_test_fs
    # file from level1_dir_without_config
    test_file = tmp_files[3]
    start_dir = (level1_dir / start_dir_modificator).resolve()

    orig_cwd = os.getcwd()
    output = [f"{start_dir = }, {test_file = }"]
    os.chdir(start_dir)
    for _ in range(2):
        # _Run adds --rcfile, which overrides config from cwd, so we need original Run here
        LintRun([*local_config_args, str(test_file)], exit=False)
        output.append(capsys.readouterr().out.replace("\\n", "\n"))

        test_file = test_file.parent
    os.chdir(orig_cwd)

    # from default config
    expected_note = "TODO"
    if start_dir_modificator == ".":
        # from config in level1_dir
        expected_note = "LEVEL1"
    assert_message = f"Wrong note after checking FILE. Readable debug output:\n{output[0]}\n{output[1]}"
    assert expected_note in output[1], assert_message
    assert_message = f"Wrong note after checking DIRECTORY. Readable debug output:\n{output[0]}\n{output[2]}"
    assert expected_note in output[2], assert_message


@pytest.mark.parametrize("test_file_index", [0, 1])
def test_subconfig_vs_cli_arg(
    _create_subconfig_test_fs: tuple[Path, ...],
    capsys: CaptureFixture,
    test_file_index: int,
) -> None:
    """Test that CLI arguments have priority over subconfigs."""
    test_root, *tmp_files = _create_subconfig_test_fs
    test_file = tmp_files[test_file_index]
    orig_cwd = os.getcwd()
    os.chdir(test_root)
    LintRun(["--notes=FIXME", "--use-local-configs=y", str(test_file)], exit=False)
    output = capsys.readouterr().out.replace("\\n", "\n")
    os.chdir(orig_cwd)

    # check that CLI argument overrides default value
    assert "TODO" not in output
    # notes=FIXME in arguments should override all pylintrc configs
    assert "ALL_LEVELS" not in output


def _create_parent_subconfig_fs(tmp_path: Path) -> Path:
    level1_dir = tmp_path / "package"
    conf_file = level1_dir / "pylintrc"
    subdir = level1_dir / "sub"
    test_file = subdir / "b.py"
    os.makedirs(subdir)
    test_file_text = "#LEVEL1\n#LEVEL2\n#TODO\n"
    test_file.write_text(test_file_text)
    conf = "[MISCELLANEOUS]\nnotes=LEVEL1,LEVEL2"
    conf_file.write_text(conf)
    return test_file


def test_subconfig_in_parent(tmp_path: Path, capsys: CaptureFixture) -> None:
    """Test that searching local configs in parent directories works."""
    test_file = _create_parent_subconfig_fs(tmp_path)
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    LintRun(["--use-local-configs=y", str(test_file)], exit=False)
    output1 = capsys.readouterr().out.replace("\\n", "\n")
    os.chdir(orig_cwd)

    # check that file is linted with config from ../, which is not a cwd
    assert "TODO" not in output1
    assert "LEVEL1" in output1


def test_register_local_config_accepts_directory(
    _create_subconfig_test_fs: tuple[Path, ...]
) -> None:
    """Test that register_local_config can handle directory as argument."""
    level1_dir, *tmp_files = _create_subconfig_test_fs
    # init linter without local configs
    linter = LintRun([str(tmp_files[0])], exit=False).linter
    level1_dir = level1_dir.resolve()
    assert level1_dir not in linter._directory_namespaces

    # call register_local_config with directory as argument
    assert level1_dir.is_dir()
    linter.register_local_config(str(level1_dir))
    assert level1_dir in linter._directory_namespaces.keys()
