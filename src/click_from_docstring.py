"""Generate ``click`` commands from function docstrings."""

import io
import uuid
import enum
import inspect
import pathlib
import datetime
import typing as t
import logging as lg

import click
import docstring_parser

__all__ = ["command"]
logger = lg.getLogger(__name__)


class _ParamArgs(enum.Enum):
    """Configuration of parameter arguments."""
    flag = "Option takes no arguments, eg '-v'"
    single = "Parameter takes one argument, eg '-o a.out'"
    multiple = "Paramater can be specified multiple times"


def _build_file_param_type(param_description: str) -> click.File:
    """Guess file mode from paramater description."""
    output = any(w in param_description for w in ("save", "output", "write"))
    mode = "w" if output else "r"
    mode += "b" if "bytes" in param_description else ""
    logger.debug("File mode guess from '%s': %s", param_description, mode)
    return click.File(mode)


def _build_path_param_type(param_description: str) -> click.Path:
    """Guess path requirements from paramater description."""
    output = any(w in param_description for w in ("save", "output", "write"))
    is_dir = "dir" in param_description
    logger.debug(
        "Path guess from '%s': output=%b, is_dir=%b",
        param_description,
        output,
        is_dir,
    )
    return click.Path(
        exists=not output,
        file_okay=not is_dir,
        dir_okay=is_dir,
        writable=output,
        readable=not output,
        allow_dash="'-'" in param_description or '"-"' in param_description
    )


def _get_param_type_from_str(
        type_name: str = None,
        param_doc: docstring_parser.DocstringParam = None,
) -> t.Tuple[_ParamArgs, t.Union[click.ParamType, None]]:
    """Guess parameter type from parameter type name."""
    type_name = type_name or ""
    desc = param_doc.description if param_doc else ""
    if type_name == "int":
        return _ParamArgs.single, int
    elif type_name == "float":
        return _ParamArgs.single, float
    elif type_name == "bytes":
        return _ParamArgs.single, bytes
    elif type_name == "bool":
        return _ParamArgs.flag, None
    elif type_name[:4] == "list":
        args, element = _get_param_type_from_str(type_name[5:-1], param_doc)
        assert args is _ParamArgs.single
        return _ParamArgs.multiple, element
    elif type_name[:5] == "tuple":
        element_names = type_name[6:-1].split(", ")
        elements = (_get_param_type_from_str(n) for n in element_names)
        return _ParamArgs.single, click.Tuple(elements)
    elif type_name == "io.FileIO":
        return _ParamArgs.single, _build_file_param_type(desc)
    elif type_name == "pathlib.Path":
        return _ParamArgs.single, _build_path_param_type(desc)
    elif type_name == "datetime.datetime":
        return _ParamArgs.single, click.DateTime()
    elif type_name == "uuid.UUID":
        return _ParamArgs.single, click.UUID
    else:
        logger.warning("Cannot guess parameter type from name: %s", type_name)
    return _ParamArgs.single, None


def _get_param_type(
        param_hint: t.Any = None,
        param_doc: docstring_parser.DocstringParam = None,
) -> t.Tuple[_ParamArgs, t.Union[click.ParamType, None]]:
    """Guess parameter type from parameter type hint."""
    desc = param_doc.description if param_doc else ""
    hint_origin = getattr(param_hint, "__origin__", type)
    if isinstance(param_hint, click.ParamType):
        return _ParamArgs.single, param_hint
    elif issubclass(param_hint, (int, float, bytes)):
        return _ParamArgs.single, param_hint
    elif issubclass(param_hint, bool):
        return _ParamArgs.flag, None
    elif issubclass(param_hint, list):
        return _ParamArgs.multiple, None
    elif issubclass(hint_origin, list):
        args, element = _get_param_type(param_hint.__args__, param_doc)
        assert args is _ParamArgs.single
        return _ParamArgs.multiple, element
    elif issubclass(hint_origin, tuple):
        elements = (_get_param_type(p) for p in param_hint.__args__)
        return _ParamArgs.single, click.Tuple(elements)
    elif issubclass(hint_origin, io.FileIO):
        return _ParamArgs.single, _build_file_param_type(desc)
    elif issubclass(hint_origin, pathlib.Path):
        return _ParamArgs.single, _build_path_param_type(desc)
    elif issubclass(hint_origin, datetime.datetime):
        return _ParamArgs.single, click.DateTime()
    elif issubclass(hint_origin, uuid.UUID):
        return _ParamArgs.single, click.UUID
    elif param_hint is None and param_doc:
        return _get_param_type_from_str(param_doc.type_name)
    else:
        logger.warning(
            "Cannot guess parameter type from type-hint: %s",
            param_hint,
        )
    return _ParamArgs.single, None


def _get_param_decorator(
        param: inspect.Parameter,
        param_args: _ParamArgs,
        param_type: click.ParamType = None,
        param_doc: docstring_parser.DocstringParam = None,
) -> t.Callable[[t.Callable], t.Callable]:
    """Construct ``click`` parameter decorator for function parameter."""
    named_param_kinds = (
        param.POSITIONAL_ONLY,
        param.POSITIONAL_OR_KEYWORD,
        param.KEYWORD_ONLY,
    )
    if param.kind in named_param_kinds:
        if param.default is param.empty:
            assert param_args is not _ParamArgs.flag
            if param_args is _ParamArgs.multiple:
                return click.argument(param.name, type=param_type, nargs=-1)
            return click.argument(param.name, type=param_type)
        else:
            name = "--" + param.name.replace("_", "-")
            multiple = None
            if param_args is _ParamArgs.flag:
                name += "/--no-" + param.name.replace("_", "-")
            elif param_args is _ParamArgs.multiple:
                multiple = True
            return click.option(
                name,
                default=param.default,
                help=param_doc.description,
                type=param_type,
                multiple=multiple,
            )
    elif param.kind == param.VAR_POSITIONAL:
        assert param_args is _ParamArgs.single
        return click.argument(param.name, type=param_type, nargs=-1)
    elif param.kind == param.VAR_KEYWORD:
        return lambda x: x  # dealt with later
    else:
        raise ValueError(param.kind)


class _CommandBuilder:
    """``click`` command builder.

    Args:
        fn: callback for command
        command_kwargs: keyword arguments to ``click.command``

    Attributes:
        command: build command
        decorators: used to build command from callback
        doc: parsed callback docstring
        param_docs: parsed callback docstring parameters
        sig: callback signature
        hints: callback type-hints
    """

    def __init__(
            self,
            fn,
            command_kwargs: t.Dict[str, t.Any] = None,
    ):
        self.fn = fn
        self.command_kwargs = command_kwargs or {}
        self.command = None  # type: t.Callable
        self.decorators = []  # type: t.List[t.Callable[[t.Callable], t.Callable]]
        self.doc = None  # type: docstring_parser.Docstring
        self.param_docs = None  # type: t.Dict[str, docstring_parser.DocstringParam]
        self.sig = None  # type: inspect.Signature
        self.hints = None  # type: t.Dict[str, t.Any]
        self.existing = set()  # type: t.Set[str]

    def _inspect_fn(self):
        """Inspect callback docstring and type-hints."""
        self.doc = docstring_parser.parse(self.fn.__doc__)
        self.param_docs = {m.arg_name: m for m in self.doc.params}
        self.sig = inspect.signature(self.fn)
        self.hints = t.get_type_hints(self.fn)
        if hasattr(self.fn, "__click_params__"):
            self.existing = set(p.name for p in self.fn.__click_params__)

    def _create_command(self):
        """Declare command."""
        kwargs = self.command_kwargs.copy()
        if "help" not in kwargs:
            kwargs["help"] = (
                self.doc.short_description +
                ("\n\n" if self.doc.blank_after_short_description else "\n") +
                self.doc.long_description
            )
        command_decorator = click.command(**kwargs)
        self.decorators.append(command_decorator)

    def _add_parameters(self):
        """Add parameters to command from callback paramaters."""
        for name, param in self.sig.parameters.items():
            if name in self.existing:
                continue
            param_doc = self.param_docs.get(name)
            param_hint = self.hints.get(name)
            param_args, param_type = _get_param_type(param_hint, param_doc)
            decorator = _get_param_decorator(param, param_args, param_type, param_doc)
            self.decorators.append(decorator)

    def _add_kwargs(self):
        """Add parameters from callback kwargs."""
        if all(p.kind != p.VAR_KEYWORD for p in self.sig.parameters.values()):
            return
        for name, param_doc in self.param_docs:
            if name in self.existing:
                continue
            param = self.sig.parameters.get(name)
            if param and param.kind != param.VAR_KEYWORD:
                continue
            param_type = _get_param_type_from_str(param_doc.type_name)
            decorator = click.option(
                "--" + name.replace("_", "-"),
                help=param_doc.description,
                type=param_type,
            )
            self.decorators.append(decorator)

    def _finalise(self):
        """Construct command from defined decorators."""
        self.command = self.fn
        for decorator in self.decorators:
            self.command = decorator(self.command)

    def build(self):
        """Build command."""
        self._inspect_fn()
        self._create_command()
        self._add_parameters()
        self._add_kwargs()
        self._finalise()


def command(**kwargs) -> t.Callable[[t.Callable], t.Callable]:  # TODO: unit-test
    """Create a ``click`` command.

    Examples:
        >>> import sys
        >>> @command
        ... def hello(n: int, stderr: bool = False):
        ...     '''Print hello N times.
        ...
        ...     Args:
        ...         n: number of greetings
        ...         stderr: print to stderr
        ...     '''
        ...     file = sys.stderr if stderr else None
        ...     for _ in range(n):
        ...         print("Hello, world!", file=file)

    Args:
        kwargs: keyword arguments to ``click.command``

    Returns:
        command-creation decorator
    """

    def wrapper(fn):
        builder = _CommandBuilder(fn, kwargs)
        builder.build()
        return builder.command
    return wrapper
