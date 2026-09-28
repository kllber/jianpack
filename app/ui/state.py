"""界面层的编辑态：把内存里的 :class:`Project` 和磁盘上的工程文件绑在一起。"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from tkinter import messagebox

from ..core import container
from ..core.errors import ProjectFileError
from ..core.paths import is_inside
from ..core.project import Project, load_project
from ..core.serialize import save_project
from ..i18n import t as _


class AppState:
    """全局状态：当前工程、是否有未保存改动、以及给外部订阅的通知。"""

    def __init__(self) -> None:
        self.project: Project | None = None
        self.dirty = False
        self._listeners: list = []
        self._quiet = 0
        # 界面当前位置（第几步、第 4 步里的哪个子标签），
        # 预览面板据此决定显示哪一页
        self.context: dict[str, object] = {"step": 0, "subtab": ""}

    # -- 订阅 ---------------------------------------------------------------

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def notify(self) -> None:
        for callback in self._listeners:
            callback()

    def touch(self) -> None:
        """控件改动后调用：标记有未保存内容并刷新标题栏。"""
        if self._quiet:
            return
        if not self.dirty:
            self.dirty = True
        self.notify()

    @contextlib.contextmanager
    def quiet(self):
        """在这个区间里刷新控件（回填模型 -> 界面）不算「用户改动」。"""
        self._quiet += 1
        try:
            yield
        finally:
            self._quiet -= 1

    # -- 生命周期 -----------------------------------------------------------

    def new_project(self, path: str | Path) -> Project:
        """新建一个**单文件**工程：磁盘上只留一个 ``.jianpack``，内容都在临时工作目录里。"""
        target = Path(path).expanduser().resolve()
        self._discard_work()
        work = container.make_work_dir()
        (work / "assets").mkdir(parents=True, exist_ok=True)
        (work / "payload").mkdir(parents=True, exist_ok=True)
        project = Project(source_path=target, base_dir=work,
                          is_container=True, work_dir=work)
        project.app.version = "1.0.0"
        project.interface.license.enabled = False
        project.interface.changelog.enabled = False
        project.build.modes = ["perMachine"]
        project.apply_derived()
        self.project = project
        self.dirty = True
        self.notify()
        return project

    def load(self, path: str | Path) -> Project:
        return self.adopt(load_project(path))

    def adopt(self, project: Project) -> Project:
        """接管一个刚读好的工程（可以在后台线程里读好，再回主线程交过来）。"""
        self._discard_work()          # 新工程读成功了才丢旧的，失败时旧的还在
        self.project = project
        self.dirty = False
        self.notify()
        return project

    def save(self, path: str | Path | None = None,
             container_mode: bool | None = None) -> Path:
        if self.project is None:
            raise ProjectFileError(_("还没有打开任何工程"))
        if path is None and not self.dirty:
            return self.project.source_path      # 没改过就不重复打包
        if path is None:
            # 早期版本的旧后缀工程：保存时自动改用新后缀；
            # 磁盘上原来那个旧文件保持不动（不删用户的东西）。
            source = self.project.source_path
            if source.suffix.lower() in container.LEGACY_EXTS:
                path = source.with_suffix(container.PROJECT_EXT)
        target = save_project(self.project, path, container_mode)
        self.dirty = False
        self.notify()
        return target

    def close(self) -> None:
        """关软件时清掉临时工作目录。"""
        self._discard_work()
        self.project = None

    def discard_payload(self, paths: list[Path]) -> None:
        """删除「从工程里移除的 payload 副本」（尽力而为，失败不打断当前操作）。"""
        for path in paths:
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    def _discard_work(self) -> None:
        if self.project is not None:
            self.project.cleanup()

    @property
    def base_dir(self) -> Path:
        if self.project is None:
            raise ProjectFileError(_("还没有打开任何工程"))
        return self.project.base_dir

    def relative_display(self, path: str | Path) -> str:
        """尽量显示成工程内相对路径，方便阅读。"""
        if self.project is None:
            return str(path)
        target = Path(path)
        if not target.is_absolute():
            return str(path)
        try:
            return target.resolve().relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            return str(target)

    # -- 把外部文件弄进工程目录 ---------------------------------------------

    def import_path(self, parent, source: str | Path, subdir: str) -> str | None:
        """把工程外的文件/文件夹纳入工程，返回写进工程文件的路径。

        已经在工程内的直接返回相对路径；在工程外的会问用户
        「复制进工程」还是「直接引用原位置」。

        返回 ``None`` 表示用户取消了操作。
        """
        src = Path(source).expanduser().resolve()
        if not src.exists():
            messagebox.showerror(_("找不到文件"),
                                 _("路径不存在：\n{path}").format(path=src),
                                 parent=parent)
            return None

        if is_inside(self.base_dir, src):
            return src.relative_to(self.base_dir.resolve()).as_posix()

        choice = messagebox.askyesnocancel(
            _("这个位置在工程目录之外"),
            _("{path}\n\n把这个文件复制一份到工程目录里吗？\n\n"
              "「是」  —— 复制到工程的 {subdir}\\ 目录。\n"
              "        好处：整个工程文件夹可以随意搬移、压缩、发给别人。\n\n"
              "「否」  —— 直接引用原来的位置。\n"
              "        注意：工程一旦移走（或发到别的电脑）就会失效。").format(
                  path=src, subdir=subdir),
            parent=parent,
            default=messagebox.YES,
            icon=messagebox.QUESTION,
        )
        if choice is None:
            return None
        if not choice:
            return str(src)

        dest_dir = self.base_dir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        if dest.exists():
            overwrite = messagebox.askyesno(
                _("同名文件已存在"),
                _("{name} 已经在 {subdir}\\ 里了，覆盖它吗？").format(
                    name=dest.name, subdir=subdir),
                parent=parent,
            )
            if not overwrite:
                return dest.relative_to(self.base_dir.resolve()).as_posix()
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            else:
                dest.unlink(missing_ok=True)

        try:
            if src.is_dir():
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)
        except OSError as exc:
            messagebox.showerror(_("复制失败"), f"{exc}", parent=parent)
            return None

        return dest.relative_to(self.base_dir.resolve()).as_posix()
