#!/usr/bin/env python
# encoding: utf-8

"""A Snippet instance is an instance of a Snippet Definition. That is, when the
user expands a snippet, a SnippetInstance is created to keep track of the
corresponding TextObjects. The Snippet itself is also a TextObject. """

from UltiSnips import _vim
from UltiSnips.position import Position
from UltiSnips.text_objects._base import EditableTextObject, \
        NoneditableTextObject

class SnippetInstance(EditableTextObject):
    """See module docstring."""
    # pylint:disable=protected-access

    def __init__(self, snippet, parent, initial_text,
            start, end, visual_content, last_re, globals):
        if start is None:
            start = Position(0, 0)
        if end is None:
            end = Position(0, 0)
        self.snippet = snippet
        self._cts = 0

        self.locals = {"match" : last_re}
        self.globals = globals
        self.visual_content = visual_content

        EditableTextObject.__init__(self, parent, start, end, initial_text)

    def replace_initial_text(self):
        """Puts the initial text of all text elements into Vim."""
        def _place_initial_text(obj):
            """recurses on the children to do the work."""
            obj.overwrite()
            if isinstance(obj, EditableTextObject):
                for child in obj._children:
                    _place_initial_text(child)
        _place_initial_text(self)

    def replay_user_edits(self, cmds):
        """Replay the edits the user has done to keep endings of our
        Text objects in sync with reality"""
        for cmd in cmds:
            self._do_edit(cmd)

    def update_textobjects(self):
        """Update the text objects that should change automagically after
        the users edits have been replayed. This might also move the Cursor
        """
        vc = _VimCursor(self)
        done = set()
        not_done = set()
        def _find_recursive(obj):
            """Finds all text objects and puts them into 'not_done'."""
            if isinstance(obj, EditableTextObject):
                for child in obj._children:
                    _find_recursive(child)
            not_done.add(obj)
        _find_recursive(self)

        counter = 10
        while (done != not_done) and counter:
            # Order matters for python locals!
            for obj in sorted(not_done - done):
                if obj._update(done):
                    done.add(obj)
            counter -= 1
        if not counter:
            raise RuntimeError(
                "The snippets content did not converge: Check for Cyclic "
                "dependencies or random strings in your snippet. You can use "
                "'if not snip.c' to make sure to only expand random output "
                "once.")
        vc.to_vim()
        self._del_child(vc)

    def select_next_tab(self, backwards=False):
        """Selects the next tabstop or the previous if 'backwards' is True."""
        if self._cts is None:
            return

        if backwards:
            cts_bf = self._cts

            res = self._get_prev_tab(self._cts)
            if res is None:
                self._cts = cts_bf
                return self._tabstops.get(self._cts, None)
            self._cts, ts = res
            return ts
        else:
            res = self._get_next_tab(self._cts)
            if res is None:
                self._cts = None
                return self._tabstops.get(0, None)
            else:
                self._cts, ts = res
                return ts

        return self._tabstops[self._cts]

    def _get_tabstop(self, requester, no):
        # SnippetInstances are completely self contained, therefore, we do not
        # need to ask our parent for Tabstops
        cached_parent = self._parent
        self._parent = None
        rv = EditableTextObject._get_tabstop(self, requester, no)
        self._parent = cached_parent
        return rv


class _VimCursor(NoneditableTextObject):
    """Helper class to keep track of the Vim Cursor when text objects expand
    and move."""

    def __init__(self, parent):
        NoneditableTextObject.__init__(
            self, parent, _vim.buf.cursor, _vim.buf.cursor,
            tiebreaker=Position(-1, -1))

    def to_vim(self):
        """Moves the cursor in the Vim to our position."""
        assert self._start == self._end
        _vim.buf.cursor = self._start
