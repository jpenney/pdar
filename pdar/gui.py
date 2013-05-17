from GUI import (Application, Document, Window, View, Grid, Label, Button,
                 Frame, Row, ModalDialog, Dialog, ScrollableView, application,
                 TextField)
from GUI.StdButtons import DefaultButton, CancelButton
from GUI.StdColors import light_grey
from GUI.Files import FileType
from GUI import FileDialogs, Alerts
from pdar.archive import PDArchive
import os
import locale
import shutil
import logging
from pdar.errors import PDARError


class PdarApplication(Application):

    def __init__(self, *args, **kwargs):
        super(PdarApplication, self).__init__(*args, **kwargs)

        self.pdar_type = FileType(name="Portable Delta Archive",
                                  suffix="pdar",
                                  mac_type="PDAR")

        self.file_type = self.pdar_type

        if locale.getlocale() == (None, None):
            locale.setlocale(locale.LC_ALL, '')

    def open_app(self):
        self.new_cmd()

    def make_document(self, file_ref=None):
        return PdarDocument(file_type=self.pdar_type)

    def make_window(self, document):
        win = None
        if document.archive:
            win = ExistingPdarWindow(document=document)
        else:
            win = Window(size=(800, 600), document=document)
            rows = []
            rows.append([Label(text='TODO')])
            grid = Grid(rows, equalize='w')
            grid.position = (10, 10)
            win.add(grid)
            win.shrink_wrap()
        win.show()


class ExistingPdarWindow(Window):

    def __init__(self, *args, **kwargs):
        super(ExistingPdarWindow, self).__init__(*args, **kwargs)
        self.backcolor = light_grey
        document = self.document
        self.archive = archive = document.archive
        self._info_window = None

        rows = []
        buttons = []
        self._path_label = TextField('', width=300)
        self._path = None
        self._output_path_label = TextField('', width=300)
        self._output_path = None
        archive_path = os.path.join(document.file.dir.path,
                                    document.file.name)
        archive_size = os.path.getsize(archive_path)
        rows.append([Label(text="PDAR Archive:"),
                     Label(text=archive_path)])
        rows.append([Label(text='PDAR Version:'),
                     Label(text=archive.pdar_version)])
        rows.append([Label(text='created:'),
                     Label(text=archive.created_datetime.strftime(
                               locale.nl_langinfo(locale.D_T_FMT)))])
        rows.append([Label(text='size:'),
                     Label(text='%s bytes' %
                           locale.format("%d", archive_size,
                                         grouping=True))])
        rows.append([
            Button(title='Path to patch',
                   action=('select_path', '_path',
                           '_path_label',
                           "Select location of files to be patched:")),
            self._path_label])
        rows.append([
            Button(title='Output path (optional)',
                   action=('select_path', '_output_path',
                           '_output_path_label',
                           "Select location where new files will be "
                           "written:")),
            self._output_path_label])
        buttons += [Button(title='More Info',
                           action='do_info_show_action'),
                    DefaultButton(title='Apply Patch')]

        buttons.append(CancelButton())
        grid = Grid(rows)
        grid.position = (10, 10)
        self.add(grid)
        self._path_label.width = self._output_path_label.width = \
            grid.contents[1].width
        self.shrink_wrap()
        button_row = Row(buttons, align='c')
        button_row.position = ((self.content_width -
                                button_row.content_width) / 2,
                               grid.bottom + 10)
        self.add(button_row)
        self.shrink_wrap()

    def select_path(self, prop, label, msg):
        result = FileDialogs.request_old_directory(msg)
        setattr(self, prop, result)
        if result:
            pth = os.path.join(result.dir.path, result.name)
            getattr(self, label).text = pth

    @property
    def info_window(self):
        if (self._info_window is None or
            self._info_window not in application().windows):
            archive = self.document.archive
            entry_info = [(entry.target,
                           locale.format("%d", len(entry.payload), grouping=True),
                           entry.type_code)
                          for entry in archive.patches]
            headings = ['File', 'Size', 'Type']
            rows = []
            for entry in sorted(entry_info,
                                key=lambda ent: ent[0].lower()):
                rows.append([Label(ent) for ent in entry])

            rows += [[Label(i) for i in headings]]
            grid = Grid(rows, align='r')
            grid.shrink_wrap()
            info = Dialog(closable=True, resizable=True)

            view = ScrollableView(
                container=info,
                size=(grid.content_width + 30 if grid.content_width < 800 else 800,
                      grid.content_height + 30
                      if grid.content_height < 600 else 600),
                extent=(grid.content_width, grid.content_height))
            view.add(Row([grid]))
            info.shrink_wrap()

            button_row = Row([Button(title='Dismiss',
                                     action=self.do_info_close_action)],
                                     align='c')
            button_row.position = ((view.content_width -
                                    button_row.content_width) / 2,
                                   view.bottom + 10)
            info.add(button_row)

            # overlay headings
            # there has to be a better way to do this, but I couldn't
            # figure it out

            heading_row = Row([Label(i) for i in headings], auto_layout=False)
            heading_row.position = view.position
            width = 0

            offset = len(grid.contents) - len(headings)
            for i, head in enumerate(heading_row.contents):
                orig = grid.contents[offset + i]
                print 'orig: %s' % orig.text
                print "orig size: %s" % str(orig.size)
                width = orig.position[0] + orig.size[0]
                height = orig.size[1]
                print "accum size: %s" % str((width, height))
                head.position = (orig.position[0], 0)
                head.size = tuple(orig.size)
                orig.size = (orig.size[0], 0)
            heading_row.size = (view.size[0], height)

            view.position = (view.position[0],
                             heading_row.position[1] + heading_row.size[1])
            view.extent = (view.extent[0], view.extent[1] - height)
            info.add(heading_row)

            info.shrink_wrap()
            self._info_window = info
        return self._info_window

    def do_info_show_action(self):
        self.info_window.show()

    def do_info_close_action(self):
        print "hiding"
        self.info_window.hide()
        if not self in application().windows:
            print "closing"
            self.info_window.close_cmd()

    def do_cancel_action(self):
        self.close_cmd()

    def do_default_action(self):
        if not self._path_label.text:
            Alerts.alert('stop', 'You must select a path to patch')
            return
        path = self._path_label.text
        output_path = self._output_path_label.text
        if not os.path.exists(path):
            Alerts.alert('stop', 'Path does not exist: %s' % path)
            return
        if output_path:
            if os.path.exists(output_path):
                Alerts.alert('stop', "Output path already exists: %s"
                             % output_path)
                return
            logging.debug("copying files '%s'->'%s'", path, output_path)
            shutil.copytree(path, output_path)
            path = output_path
        else:
            if not Alerts.alert2('caution',
                                 "You have not set an output path.\n"
                                 "The original files will be overwritten.\n\n"
                                 "Do you wish to continue?"):
                return
        handler = PdarGUILogHandler()
        logging.getLogger().addHandler(handler)

        try:
            self.archive.patch(path)
        except PDARError, err:
            Alerts.alert('stop', "Error applying patch\n%s" % str(err))
            return
        Alerts.alert('note', "Patch applied successfully")
        self.close_cmd()


class PdarGUILogHandler(logging.Handler):

    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)

        self._dialog = Dialog(closable=True, resizable=True, size=(800, 600))
        self._view = ScrollableView(
                container=self._dialog,
                size=(self._dialog.width - 20, self._dialog.height - 20))
        self._view.extent = (self._view.width / 2, self._view.height - 10)
        self._view.position = (10, 10)
        self._dialog.shrink_wrap()
        self._dialog.show()
        self._view.update()
        self._next_position = (0, 0)

    def emit(self, record):
        print "MY HANDLER: %s" % self.format(record)
        label = Label(self.format(record))
        label.position = self._next_position
        self._view.extent = (label.right
                             if label.right > self._view.extent[0]
                             else self._view.extent[0],
                             self._next_position[1] + (label.height * 2))
        self._view.add(label)
        self._next_position = (label.left, label.top + label.height)
        self._view.scroll_offset = self._next_position
        self._view.update()


class PdarDocument(Document):

    def __init__(self, *args, **kwargs):
        super(PdarDocument, self).__init__(*args, **kwargs)
        self.archive = None

    def new_contents(self):
        pass

    def read_contents(self, file_):
        self.archive = PDArchive.load_archive(file_)

    def write_contents(self, file_):
        self.archive.save_archive(file_)


if __name__ == '__main__':

    logging.basicConfig(format="%(message)s",
                        level=logging.DEBUG)
    PdarApplication(title='PDAR GUI').run()
