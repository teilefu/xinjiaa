# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════
  星迹日历 · 安卓版  (Python + Kivy)
  - 月视图：阳历+阴历+节气+节日+调休，当天标红
  - 年视图：12个月总览，日历栏左上角切换
  - 纪念日：左右滑动卡片流（灵动感），倒计时+经历天数
  - 编辑页：命名 / 自定义图片 / 阳历提醒 / 阴历提醒
  - 节假日：法定节假日 + 二十四节气，固定列表+倒计时
  - 数据本地JSON保存，无需登录；到日子手机弹窗提醒
═══════════════════════════════════════════════════
"""
import json
import os
import uuid
import shutil
import platform
from datetime import date, timedelta

from kivy.app import App
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.carousel import Carousel
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.filechooser import FileChooserListView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp

from lunar_python import Solar, Lunar

# ───────────────────────── 全局配置 ─────────────────────────
FONT = 'NotoSansSC-Regular.otf'
FONT_B = 'NotoSansSC-Bold.otf'
LabelBase.register(name='zh', fn_regular=FONT, fn_bold=FONT_B)

RED    = '#e64545'   # 节日/今天/倒计时
ORANGE = '#e67e22'   # 节气
BLUE   = '#3b82f6'   # 主色
DARK   = '#222222'
GRAY   = '#8a9096'
LIGHT  = '#f5f6f8'
LINE   = '#eceef0'

GRAD_CARDS = [  # 卡片渐变配色
    ('#ff8a3d', '#ff5f6d'),
    ('#5b8cff', '#7c5bff'),
    ('#00b894', '#00a3d4'),
    ('#f368e0', '#8e44ad'),
    ('#f39c12', '#e74c3c'),
    ('#27ae60', '#16a085'),
]


def L(text='', **kw):
    kw.setdefault('font_name', 'zh')
    return Label(text=text, **kw)


def B(text='', **kw):
    kw.setdefault('font_name', 'zh')
    return Button(text=text, **kw)


# ───────────────────────── 日期/农历/节气工具 ─────────────────────────

def lunar_of(d):
    return Solar.fromYmd(d.year, d.month, d.day).getLunar()


def lunar_text(d):
    lun = lunar_of(d)
    return lun.getMonthInChinese() + '月' + lun.getDayInChinese()


def jieqi_text(d):
    return lunar_of(d).getJieQi() or ''


LUNAR_FEST = {(1,1):'春节',(1,15):'元宵节',(5,5):'端午节',(7,7):'七夕节',
              (8,15):'中秋节',(9,9):'重阳节',(12,8):'腊八节',(12,23):'小年'}

def lunar_festival(d):
    lun = lunar_of(d)
    return LUNAR_FEST.get((lun.getMonth(), lun.getDay()), '')


SOLAR_FEST = {(1,1):'元旦',(2,14):'情人节',(3,8):'妇女节',(3,12):'植树节',
              (4,1):'愚人节',(5,1):'劳动节',(5,4):'青年节',(6,1):'儿童节',
              (7,1):'建党节',(8,1):'建军节',(9,10):'教师节',(10,1):'国庆节',
              (12,24):'平安夜',(12,25):'圣诞节'}

def solar_festival(d):
    return SOLAR_FEST.get((d.month, d.day), '')


JIEQI_LIST = ['小寒','大寒','立春','雨水','惊蛰','春分','清明','谷雨','立夏','小满',
              '芒种','夏至','小暑','大暑','立秋','处暑','白露','秋分','寒露','霜降',
              '立冬','小雪','大雪','冬至']
_jq_cache = {}

def jieqi_dates(year):
    if year in _jq_cache:
        return _jq_cache[year]
    res = {}
    d = date(year, 1, 1)
    while d.year == year:
        jq = jieqi_text(d)
        if jq and jq not in res:
            res[jq] = d
        d += timedelta(days=1)
    _jq_cache[year] = res
    return res


def next_yearly_solar(m, d, today_):
    x = date(today_.year, m, d)
    if x < today_:
        x = date(today_.year + 1, m, d)
    return x


def next_yearly_lunar(lm, ld, today_):
    for y in (today_.year, today_.year + 1):
        try:
            s = Lunar.fromYmd(y, lm, ld).getSolar()
            x = date(s.getYear(), s.getMonth(), s.getDay())
            if x >= today_:
                return x
        except Exception:
            continue
    return today_


def parse_md(s, sep='-'):
    a = [int(x) for x in str(s).strip().replace('/', sep).split(sep)]
    if len(a) >= 3:          # YYYY-MM-DD → 只取 月-日
        return a[1], a[2]
    if len(a) >= 2:
        return a[0], a[1]
    return 1, 1


def parse_ymd(s):
    a = [int(x) for x in str(s).strip().replace('/', '-').split('-')]
    if len(a) >= 3:
        return date(a[0], a[1], a[2])
    return None


def today():
    return date.today()


# ───────────────────────── 数据层（本地JSON） ─────────────────────────

def data_file(app):
    return os.path.join(app.user_data_dir, 'xingji_data.json')


def load_data(app):
    p = data_file(app)
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d, dict) and 'memorials' in d:
                return d
        except Exception:
            pass
    return {'memorials': []}


def save_data(app, data):
    p = data_file(app)
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('保存失败:', e)


def first_date(m):
    try:
        return date(*[int(x) for x in m['start_solar'].split('-')])
    except Exception:
        return today()


def next_date(m, today_):
    if m.get('repeat') == 'once':
        return first_date(m)
    if m.get('start_type') == 'lunar':
        lm, ld = parse_md(m.get('start_lunar', '1-1'))
        return next_yearly_lunar(lm, ld, today_)
    mm, dd = parse_md(m.get('start_solar', '1-1'))
    return next_yearly_solar(mm, dd, today_)


def remain_days(m, today_):
    return (next_date(m, today_) - today_).days


def passed_days(m, today_):
    return (today_ - first_date(m)).days


# ───────────────────────── 通用组件 ─────────────────────────

def set_gradient(widget, c1, c2, steps=28):
    """在 widget.canvas.before 画垂直渐变（c1上→c2下）"""
    w, h = widget.size
    if w <= 0 or h <= 0:
        return
    ca = get_color_from_hex(c1)
    cb = get_color_from_hex(c2)
    for i in range(steps):
        t = i / (steps - 1)
        r = ca[0] + (cb[0] - ca[0]) * t
        g = ca[1] + (cb[1] - ca[1]) * t
        b = ca[2] + (cb[2] - ca[2]) * t
        y0 = h * (1 - (i + 1) / steps)
        y1 = h * (1 - i / steps)
        widget.canvas.before.add(Color(r, g, b, 1))
        widget.canvas.before.add(Rectangle(pos=(0, y0), size=(w, y1 - y0)))


class TabBar(BoxLayout):
    """底部三大项标签：日历 / 纪念日 / 节假日"""
    def __init__(self, app, current, **kw):
        super().__init__(**kw)
        self.app = app
        self.spacing = dp(0)
        self.size_hint_y = None
        self.height = dp(54)
        items = [('main', '日历', '📅'), ('cards', '纪念日', '❤️'), ('holidays', '节假日', '🏮')]
        for key, name, icon in items:
            color = BLUE if key == current else GRAY
            size = sp(19) if key == 'cards' else sp(16)   # 中间纪念日更突出
            btn = B('', size_hint=(1, 1))
            btn.text = '[color=%s]%s\n%s[/color]' % (color, icon, name)
            btn.markup = True
            btn.font_size = size
            btn.background_color = (1, 1, 1, 1)
            btn.color = (1, 1, 1, 1)
            btn.bold = (key == 'cards')
            btn.bind(on_release=lambda b, k=key: self.app.switch_tab(k))
            self.add_widget(btn)


class MonthGrid(GridLayout):
    """某年某月的日历格子"""
    def __init__(self, app, year, month, on_day=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.cols = 7
        self.spacing = dp(2)
        self.padding = [dp(6), dp(4), dp(6), dp(4)]
        t = today()
        first = date(year, month, 1)
        # 周一开头
        offset = first.weekday()
        days = 31
        if month in (4, 6, 9, 11):
            days = 30
        elif month == 2:
            days = 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28
        for _ in range(offset):
            self.add_widget(BoxLayout())  # 空白
        for day in range(1, days + 1):
            d = date(year, month, day)
            is_today = (d == t)
            self.add_widget(self._cell(d, is_today, on_day))

    def _cell(self, d, is_today, on_day):
        box = BoxLayout(orientation='vertical', padding=[0, dp(1), 0, dp(1)])
        with box.canvas.before:
            Color(0.95, 0.96, 0.97, 1) if is_today else Color(1, 1, 1, 1)
            Rectangle(pos=box.pos, size=box.size)

        num = Label(text=str(d.day), font_name='zh', font_size=sp(16),
                    color=get_color_from_hex(RED if is_today else DARK),
                    bold=True, size_hint=(1, None), height=dp(22))
        if is_today:
            num.text = '[color=%s]● %d[/color]' % (RED, d.day)
            num.markup = True
        # 底部标注：节气>节日>调休>阴历
        tag, tag_color = '', GRAY
        jq = jieqi_text(d)
        if jq:
            tag, tag_color = jq, ORANGE
        else:
            sf = solar_festival(d)
            lf = lunar_festival(d)
            if sf or lf:
                tag, tag_color = (sf or lf), RED
            else:
                tag = lunar_text(d)
        sub = Label(text=tag, font_name='zh', font_size=sp(10),
                    color=get_color_from_hex(tag_color),
                    halign='center', size_hint=(1, None), height=dp(16))
        sub.text_size = (None, None)
        box.add_widget(num)
        box.add_widget(sub)

        def on_touch(bx, touch):
            if bx.collide_point(*touch.pos):
                if on_day:
                    on_day(d)
                return True
            return False
        box.on_touch_down = on_touch.__get__(box, BoxLayout)
        return box


class MemRow(BoxLayout):
    """月历下方的纪念日列表行：名字 · 经历天数 + 起始日期"""
    def __init__(self, app, mem, **kw):
        super().__init__(**kw)
        self.app = app
        self.padding = [dp(14), dp(10)]
        self.spacing = dp(8)
        self.size_hint_y = None
        self.height = dp(58)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.93, 0.94, 0.95, 1)
            Rectangle(pos=(self.x, self.y), size=(self.width, 1))
        p = passed_days(mem, today())
        left = BoxLayout(orientation='vertical', spacing=dp(2))
        name_l = L(mem['name'], font_size=sp(16), bold=True, color=get_color_from_hex(DARK))
        sub_txt = '纪念日丨%s' % mem.get('start_solar', '')
        sub = L(sub_txt, font_size=sp(12), color=get_color_from_hex(GRAY))
        left.add_widget(name_l)
        left.add_widget(sub)
        right = L('%d天' % p, font_size=sp(16), bold=True, color=get_color_from_hex(RED))
        self.add_widget(left)
        self.add_widget(right)
        self.bind(on_touch_down=self._tap)

    def _tap(self, box, touch):
        if box.collide_point(*touch.pos):
            self.app.open_edit(self.app.mem_index(self.mem_id if hasattr(self, 'mem_id') else ''))
            return True
        return False


# ───────────────────────── 屏幕：主界面（月历） ─────────────────────────

class MainScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.year = today().year
        self.month = today().month
        self.cur_date = today()
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')
        # 顶栏
        head = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(12), 0])
        title = L('', font_size=sp(22), bold=True, color=get_color_from_hex(DARK))
        self.title = title
        head.add_widget(title)
        yb = B('年视图', size_hint=(None, None), size=(dp(70), dp(32)),
               background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1),
               font_size=sp(14))
        yb.bind(on_release=lambda *a: self.app.show_year(self.year))
        head.add_widget(yb)
        addb = B('＋', size_hint=(None, None), size=(dp(36), dp(32)),
                 background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1),
                 font_size=sp(20), bold=True)
        addb.bind(on_release=lambda *a: self.app.open_edit(None))
        head.add_widget(addb)
        root.add_widget(head)
        # 星期
        wk = GridLayout(cols=7, size_hint_y=None, height=dp(24))
        for w in ['一', '二', '三', '四', '五', '六', '日']:
            wk.add_widget(L(w, font_size=sp(12), color=get_color_from_hex(GRAY)))
        root.add_widget(wk)
        # 月历
        self.grid_box = BoxLayout()
        root.add_widget(self.grid_box, 2)
        # 纪念日列表（与卡片流同步）
        mem_title = L('纪念日', font_size=sp(14), bold=True,
                      color=get_color_from_hex(DARK), size_hint_y=None, height=dp(32))
        root.add_widget(mem_title)
        sv = ScrollView()
        self.mem_list = BoxLayout(orientation='vertical')
        self.mem_list.size_hint_y = None
        sv.add_widget(self.mem_list)
        root.add_widget(sv, 3)
        # 底部标签
        root.add_widget(TabBar(self.app, 'main'))
        self.refresh()
        self.add_widget(root)

    def refresh(self):
        self.year = self.cur_date.year
        self.month = self.cur_date.month
        self.title.text = '%d年%d月' % (self.year, self.month)
        self.grid_box.clear_widgets()
        self.grid_box.add_widget(MonthGrid(self.app, self.year, self.month,
                                           on_day=self.app.show_day_detail))
        self.refresh_mem_list()

    def refresh_mem_list(self):
        self.mem_list.clear_widgets()
        m = self.app.data.get('memorials', [])
        if not m:
            self.mem_list.add_widget(L('还没有纪念日，点右上角 ＋ 添加',
                                       font_size=sp(13), color=get_color_from_hex(GRAY),
                                       size_hint_y=None, height=dp(60)))
            return
        for mem in m:
            row = MemRow(self.app, mem)
            row.mem_id = mem.get('id', '')
            self.mem_list.add_widget(row)


# ───────────────────────── 屏幕：年视图 ─────────────────────────

class YearScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.year = today().year
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')
        head = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), 0])
        pre = B('◀', size_hint=(None, None), size=(dp(40), dp(32)), font_size=sp(18))
        pre.bind(on_release=lambda *a: self.set_year(self.year - 1))
        head.add_widget(pre)
        self.title = L('%d年' % self.year, font_size=sp(22), bold=True,
                       color=get_color_from_hex(DARK), size_hint=(1, 1))
        head.add_widget(self.title)
        nxt = B('▶', size_hint=(None, None), size=(dp(40), dp(32)), font_size=sp(18))
        nxt.bind(on_release=lambda *a: self.set_year(self.year + 1))
        head.add_widget(nxt)
        mbtn = B('月视图', size_hint=(None, None), size=(dp(70), dp(32)),
                 background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1),
                 font_size=sp(14))
        mbtn.bind(on_release=lambda *a: self.app.back_to_month())
        head.add_widget(mbtn)
        root.add_widget(head)
        # 12个月 3列x4行
        g = GridLayout(cols=3, spacing=dp(4), padding=[dp(6), dp(4)])
        self.months = {}
        for mon in range(1, 13):
            mb = BoxLayout(orientation='vertical')
            t = today()
            with mb.canvas.before:
                Color(1, 1, 1, 1)
                Rectangle(pos=mb.pos, size=mb.size)
            mt = L('%d月' % mon, font_size=sp(11), bold=True, color=get_color_from_hex(BLUE),
                   size_hint_y=None, height=dp(18))
            mb.add_widget(mt)
            mg = MonthGrid(self.app, self.year, mon,
                           on_day=self.app.year_day_click, spacing=0)
            mg.padding = [1, 0, 1, 0]
            mb.add_widget(mg)
            g.add_widget(mb)
            self.months[mon] = mb
        root.add_widget(g)
        root.add_widget(TabBar(self.app, 'main'))
        self.add_widget(root)

    def set_year(self, y):
        self.year = y
        self.title.text = '%d年' % y
        for mon, mb in self.months.items():
            mb.clear_widgets()
            mt = L('%d月' % mon, font_size=sp(11), bold=True, color=get_color_from_hex(BLUE),
                   size_hint_y=None, height=dp(18))
            mb.add_widget(mt)
            mb.add_widget(MonthGrid(self.app, y, mon, on_day=self.app.year_day_click))


# ───────────────────────── 屏幕：纪念日卡片流 ─────────────────────────

class MemCard(FloatLayout):
    """一张纪念日卡片：渐变/图片背景 + 名字 + 大号倒计时 + 经历天数 + 按钮"""
    def __init__(self, app, mem, **kw):
        super().__init__(**kw)
        self.app = app
        self.mem = mem
        t = today()
        days = remain_days(mem, t)
        passed = passed_days(mem, t)
        name = mem.get('name', '未命名')
        c1, c2 = GRAD_CARDS[hash(mem.get('id', '')) % len(GRAD_CARDS)]
        self.c1, self.c2 = c1, c2

        # 背景
        img = mem.get('image', '')
        if img and os.path.exists(img):
            ki = KivyImage(source=img, allow_stretch=True, keep_ratio=False,
                           pos_hint={'x': 0, 'y': 0}, size_hint=(1, 1))
            self.add_widget(ki)
            with self.canvas.before:
                Color(0, 0, 0, 0.30)
                Rectangle(pos=self.pos, size=self.size)
        else:
            set_gradient(self, c1, c2)

        pad = dp(16)
        # 左上：起始日期
        top_l = L('', font_size=sp(12), color=(1, 1, 1, 0.92),
                  pos_hint={'x': 0, 'y': 0.86}, size_hint=(None, None))
        s = mem.get('start_solar', '')
        extra = ''
        if mem.get('start_type') == 'lunar':
            extra = '（农历%s）' % mem.get('start_lunar', '')
        top_l.text = '%s\n%s' % (s, extra.strip('（）') or '')
        top_l.text_size = (dp(150), None)
        self.add_widget(top_l)
        # 右上：名字（胶囊）
        nm = L(name, font_size=sp(17), bold=True, color=(1, 1, 1, 1),
               pos_hint={'right': 1, 'top': 0.93}, size_hint=(None, None))
        nm.texture_update()
        nm.size = (nm.texture_size[0] + dp(26), dp(34))
        with nm.canvas.before:
            Color(1, 1, 1, 0.22)
            RoundedRectangle(pos=nm.pos, size=nm.size, radius=[dp(17)])
        self.add_widget(nm)
        # 中央：大号倒计时
        if days >= 0:
            num = L('', font_size=sp(76), bold=True, color=(1, 1, 1, 1),
                    halign='center', pos_hint={'x': 0, 'y': 0.34}, size_hint=(1, None),
                    height=dp(120))
            num.text = '[size=26]还有[/size]\n[size=92][b]%d[/b][/size][size=26]天[/size]' % days
            num.markup = True
            num.text_size = (dp(320), dp(120))
        else:
            num = L('已到期', font_size=sp(40), bold=True, color=(1, 1, 1, 0.9),
                    halign='center', pos_hint={'x': 0, 'y': 0.4}, size_hint=(1, None),
                    height=dp(80))
        self.add_widget(num)
        # 经历天数
        exp = L('已经历 %d 天' % passed, font_size=sp(15), bold=True, color=(1, 1, 1, 0.95),
                halign='center', pos_hint={'x': 0, 'y': 0.26}, size_hint=(1, None),
                height=dp(26))
        self.add_widget(exp)
        # 底部按钮条
        btns = BoxLayout(size_hint=(1, None), height=dp(40), padding=[dp(8), 0],
                         pos_hint={'x': 0, 'y': 0.03}, spacing=dp(8))
        edit_b = B('✏ 编辑', size_hint=(None, None), size=(dp(80), dp(34)),
                   background_color=(1, 1, 1, 0.25), color=(1, 1, 1, 1), font_size=sp(13))
        edit_b.bind(on_release=lambda *a: self.app.open_edit(mem.get('id')))
        rem_txt = {'solar': '⏰ 阳历提醒', 'lunar': '⏰ 阴历提醒'}.get(mem.get('remind', ''), '⏰ 未设提醒')
        rem_b = B(rem_txt, size_hint=(None, None), size=(dp(140), dp(34)),
                  background_color=(1, 1, 1, 0.25), color=(1, 1, 1, 1), font_size=sp(13))
        rem_b.bind(on_release=lambda *a: self.app.open_edit(mem.get('id')))
        del_b = B('🗑 删除', size_hint=(None, None), size=(dp(80), dp(34)),
                  background_color=(1, 1, 1, 0.25), color=(1, 1, 1, 1), font_size=sp(13))
        del_b.bind(on_release=lambda *a: self.app.confirm_delete(mem.get('id')))
        btns.add_widget(edit_b)
        btns.add_widget(rem_b)
        btns.add_widget(del_b)
        self.add_widget(btns)
        # 点击卡片本身也进编辑
        self.bind(on_touch_down=self._tap)

    def _tap(self, box, touch):
        if box.collide_point(*touch.pos):
            # 避免点按钮也触发
            return False
        return False


class CardsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')
        head = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(12), 0])
        head.add_widget(L('纪念日', font_size=sp(22), bold=True,
                          color=get_color_from_hex(DARK)))
        addb = B('＋', size_hint=(None, None), size=(dp(36), dp(32)),
                 background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1),
                 font_size=sp(20), bold=True)
        addb.bind(on_release=lambda *a: self.app.open_edit(None))
        head.add_widget(addb)
        root.add_widget(head)
        self.car = Carousel(direction='right', loop=False, anim_move_duration=0.35)
        root.add_widget(self.car, 1)
        # 指示点
        self.dots = BoxLayout(size_hint_y=None, height=dp(24), padding=[0, dp(6)])
        root.add_widget(self.dots)
        root.add_widget(TabBar(self.app, 'cards'))
        self.refresh()
        self.add_widget(root)

    def refresh(self):
        self.car.clear_widgets()
        m = self.app.data.get('memorials', [])
        if not m:
            self.car.add_widget(L('还没有纪念日\n点右上角 ＋ 添加',
                                  font_size=sp(16), color=get_color_from_hex(GRAY),
                                  halign='center', valign='middle'))
            return
        for mem in m:
            card = MemCard(self.app, mem)
            card.size_hint = (0.9, 1.0)
            self.car.add_widget(card)
        self._refresh_dots()

    def _refresh_dots(self):
        self.dots.clear_widgets()
        n = len(self.app.data.get('memorials', []))
        for i in range(n):
            w = dp(18) if i == self.car.index else dp(6)
            c = BLUE if i == self.car.index else '#d4d8dd'
            d = Label(text='', size_hint=(None, None), size=(w, dp(6)))
            with d.canvas.before:
                Color(*get_color_from_hex(c))
                RoundedRectangle(pos=d.pos, size=d.size, radius=[dp(3)])
            self.dots.add_widget(d)
        self.car.bind(on_index=self._on_index)

    def _on_index(self, *a):
        self._refresh_dots()


# ───────────────────────── 屏幕：编辑页 ─────────────────────────

class EditScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.mem_id = None
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')
        head = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), 0])
        back = B('‹ 返回', size_hint=(None, None), size=(dp(64), dp(32)), font_size=sp(15))
        back.bind(on_release=lambda *a: self.app.back_from_edit())
        head.add_widget(back)
        self.title = L('添加纪念日', font_size=sp(19), bold=True, color=get_color_from_hex(DARK))
        head.add_widget(self.title)
        root.add_widget(head)

        sv = ScrollView()
        form = BoxLayout(orientation='vertical', padding=[dp(14), dp(6)], spacing=dp(10))
        form.size_hint_y = None
        form.bind(minimum_height=form.setter('height'))

        # 1 命名
        form.add_widget(self._field_label('1. 命名'))
        self.name_inp = TextInput(font_name='zh', hint_text='请输入纪念日名字',
                                  size_hint_y=None, height=dp(44), multiline=False)
        form.add_widget(self.name_inp)

        # 2 图片
        form.add_widget(self._field_label('2. 自定义图片'))
        self.img_preview = BoxLayout(size_hint_y=None, height=dp(110))
        with self.img_preview.canvas.before:
            Color(0.96, 0.97, 0.98, 1)
            Rectangle(pos=self.img_preview.pos, size=self.img_preview.size)
        self.img_label = L('点击下方按钮选择图片', color=get_color_from_hex(GRAY),
                           font_size=sp(13))
        self.img_preview.add_widget(self.img_label)
        form.add_widget(self.img_preview)
        img_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        pick = B('选择图片', background_color=get_color_from_hex(BLUE),
                 color=(1, 1, 1, 1), font_size=sp(14))
        pick.bind(on_release=lambda *a: self.pick_image())
        clr = B('清除图片', background_color=get_color_from_hex('#e74c3c'),
                color=(1, 1, 1, 1), font_size=sp(14))
        clr.bind(on_release=lambda *a: self.clear_image())
        img_row.add_widget(pick)
        img_row.add_widget(clr)
        form.add_widget(img_row)
        self.image_path = ''

        # 3 起始日期类型
        form.add_widget(self._field_label('3. 起始日期（用于算经历天数）'))
        st_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.st_solar = ToggleButton(text='阳历', font_name='zh', font_size=sp(14),
                                     size_hint=(1, 1), group='st', state='down',
                                     background_color=get_color_from_hex(BLUE),
                                     color=(1, 1, 1, 1))
        self.st_lunar = ToggleButton(text='阴历', font_name='zh', font_size=sp(14),
                                     size_hint=(1, 1), group='st',
                                     background_color=get_color_from_hex('#cfd4da'),
                                     color=(1, 1, 1, 1))
        self.st_solar.bind(on_press=lambda *a: self._st_color())
        self.st_lunar.bind(on_press=lambda *a: self._st_color())
        st_row.add_widget(self.st_solar)
        st_row.add_widget(self.st_lunar)
        form.add_widget(st_row)
        # 阳历输入
        self.solar_box = BoxLayout(orientation='vertical', spacing=dp(4))
        self.solar_inp = TextInput(font_name='zh', hint_text='阳历日期，如 1974-08-20',
                                   size_hint_y=None, height=dp(42), multiline=False)
        self.solar_box.add_widget(self.solar_inp)
        form.add_widget(self.solar_box)
        # 阴历输入
        self.lunar_box = BoxLayout(orientation='vertical', spacing=dp(4))
        lr = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.lunar_year = TextInput(font_name='zh', hint_text='年份', multiline=False,
                                    size_hint=(0.4, 1))
        self.lunar_md = TextInput(font_name='zh', hint_text='农历月-日，如 8-20', multiline=False,
                                  size_hint=(0.6, 1))
        lr.add_widget(self.lunar_year)
        lr.add_widget(self.lunar_md)
        self.lunar_box.add_widget(lr)
        form.add_widget(self.lunar_box)

        # 4 重复
        form.add_widget(self._field_label('4. 重复方式'))
        rp_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.rp_yearly = ToggleButton(text='每年重复', font_name='zh', font_size=sp(14),
                                      size_hint=(1, 1), group='rp', state='down',
                                      background_color=get_color_from_hex(BLUE),
                                      color=(1, 1, 1, 1))
        self.rp_once = ToggleButton(text='仅一次', font_name='zh', font_size=sp(14),
                                    size_hint=(1, 1), group='rp',
                                    background_color=get_color_from_hex('#cfd4da'),
                                    color=(1, 1, 1, 1))
        self.rp_yearly.bind(on_press=lambda *a: self._rp_color())
        self.rp_once.bind(on_press=lambda *a: self._rp_color())
        rp_row.add_widget(self.rp_yearly)
        rp_row.add_widget(self.rp_once)
        form.add_widget(rp_row)

        # 5 提醒
        form.add_widget(self._field_label('5. 提醒（到日子手机弹窗）'))
        rm_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.rm_none = ToggleButton(text='不提醒', font_name='zh', font_size=sp(13),
                                    size_hint=(1, 1), group='rm', state='down',
                                    background_color=get_color_from_hex(BLUE),
                                    color=(1, 1, 1, 1))
        self.rm_solar = ToggleButton(text='阳历提醒', font_name='zh', font_size=sp(13),
                                     size_hint=(1, 1), group='rm',
                                     background_color=get_color_from_hex('#cfd4da'),
                                     color=(1, 1, 1, 1))
        self.rm_lunar = ToggleButton(text='阴历提醒', font_name='zh', font_size=sp(13),
                                     size_hint=(1, 1), group='rm',
                                     background_color=get_color_from_hex('#cfd4da'),
                                     color=(1, 1, 1, 1))
        for b in (self.rm_none, self.rm_solar, self.rm_lunar):
            b.bind(on_press=lambda *a: self._rm_color())
        rm_row.add_widget(self.rm_none)
        rm_row.add_widget(self.rm_solar)
        rm_row.add_widget(self.rm_lunar)
        form.add_widget(rm_row)
        self.rm_solar_box = BoxLayout(orientation='vertical', spacing=dp(4))
        self.rm_solar_inp = TextInput(font_name='zh', hint_text='阳历提醒 月-日，如 03-03',
                                      size_hint_y=None, height=dp(42), multiline=False)
        self.rm_solar_box.add_widget(self.rm_solar_inp)
        form.add_widget(self.rm_solar_box)
        self.rm_lunar_box = BoxLayout(orientation='vertical', spacing=dp(4))
        self.rm_lunar_inp = TextInput(font_name='zh', hint_text='阴历提醒 月-日，如 01-15',
                                      size_hint_y=None, height=dp(42), multiline=False)
        self.rm_lunar_box.add_widget(self.rm_lunar_inp)
        form.add_widget(self.rm_lunar_box)

        # 保存 / 删除
        save = B('保存', size_hint_y=None, height=dp(46),
                 background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1),
                 font_size=sp(17), bold=True)
        save.bind(on_release=lambda *a: self.save())
        form.add_widget(save)
        self.del_btn = B('删除这个纪念日', size_hint_y=None, height=dp(44),
                         background_color=get_color_from_hex('#e74c3c'),
                         color=(1, 1, 1, 1), font_size=sp(15))
        self.del_btn.bind(on_release=lambda *a: self.app.confirm_delete(self.mem_id, back=True))
        form.add_widget(self.del_btn)

        sv.add_widget(form)
        root.add_widget(sv)
        self.add_widget(root)

    @staticmethod
    def _field_label(t):
        return L(t, font_size=sp(14), bold=True, color=get_color_from_hex(DARK),
                 size_hint_y=None, height=dp(24))

    def _st_color(self):
        for b, on in ((self.st_solar, self.st_solar.state == 'down'),
                      (self.st_lunar, self.st_lunar.state == 'down')):
            b.background_color = get_color_from_hex(BLUE if on else '#cfd4da')
            b.color = (1, 1, 1, 1)
        self.solar_box.disabled = self.st_solar.state != 'down'
        self.lunar_box.disabled = self.st_lunar.state != 'down'

    def _rp_color(self):
        for b, on in ((self.rp_yearly, self.rp_yearly.state == 'down'),
                      (self.rp_once, self.rp_once.state == 'down')):
            b.background_color = get_color_from_hex(BLUE if on else '#cfd4da')
            b.color = (1, 1, 1, 1)

    def _rm_color(self):
        for b, on in ((self.rm_none, self.rm_none.state == 'down'),
                      (self.rm_solar, self.rm_solar.state == 'down'),
                      (self.rm_lunar, self.rm_lunar.state == 'down')):
            b.background_color = get_color_from_hex(BLUE if on else '#cfd4da')
            b.color = (1, 1, 1, 1)
        self.rm_solar_box.disabled = self.rm_solar.state != 'down'
        self.rm_lunar_box.disabled = self.rm_lunar.state != 'down'
        self.rm_solar_box.opacity = 1 if self.rm_solar.state == 'down' else 0.3
        self.rm_lunar_box.opacity = 1 if self.rm_lunar.state == 'down' else 0.3

    def load(self, mem):
        self.mem_id = mem.get('id') if mem else None
        self.title.text = '编辑纪念日' if mem else '添加纪念日'
        self.del_btn.disabled = not mem
        self.del_btn.opacity = 1 if mem else 0.3
        self.name_inp.text = mem.get('name', '') if mem else ''
        self.image_path = mem.get('image', '') if mem else ''
        self._show_img()
        if mem:
            if mem.get('start_type') == 'lunar':
                self.st_lunar.state = 'down'
                self.st_solar.state = 'normal'
                lm, ld = parse_md(mem.get('start_lunar', '1-1'))
                fy = first_date(mem)
                self.lunar_year.text = str(fy.year)
                self.lunar_md.text = '%d-%d' % (lm, ld)
            else:
                self.st_solar.state = 'down'
                self.st_lunar.state = 'normal'
                self.solar_inp.text = mem.get('start_solar', '')
            self.rp_yearly.state = 'down' if mem.get('repeat', 'yearly') == 'yearly' else 'normal'
            self.rp_once.state = 'normal' if self.rp_yearly.state == 'down' else 'down'
            rm = mem.get('remind', '')
            self.rm_none.state = 'down' if rm == '' else 'normal'
            self.rm_solar.state = 'down' if rm == 'solar' else 'normal'
            self.rm_lunar.state = 'down' if rm == 'lunar' else 'normal'
            self.rm_solar_inp.text = mem.get('remind_solar', '')
            self.rm_lunar_inp.text = mem.get('remind_lunar', '')
        else:
            self.st_solar.state = 'down'
            self.st_lunar.state = 'normal'
            self.rp_yearly.state = 'down'
            self.rp_once.state = 'normal'
            self.rm_none.state = 'down'
            self.rm_solar.state = 'normal'
            self.rm_lunar.state = 'normal'
            self.solar_inp.text = ''
            self.lunar_year.text = str(today().year)
            self.lunar_md.text = ''
            self.rm_solar_inp.text = ''
            self.rm_lunar_inp.text = ''
        self._st_color()
        self._rp_color()
        self._rm_color()

    def _show_img(self):
        self.img_preview.clear_widgets()
        if self.image_path and os.path.exists(self.image_path):
            ki = KivyImage(source=self.image_path, allow_stretch=True,
                           keep_ratio=False, size_hint=(1, 1))
            self.img_preview.add_widget(ki)
        else:
            self.img_label = L('点击下方按钮选择图片', color=get_color_from_hex(GRAY),
                               font_size=sp(13))
            self.img_preview.add_widget(self.img_label)

    def pick_image(self):
        def on_pick(selection):
            if selection:
                src = selection[0]
                dst_dir = os.path.join(App.get_running_app().user_data_dir, 'images')
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                except Exception:
                    pass
                ext = os.path.splitext(src)[1] or '.jpg'
                dst = os.path.join(dst_dir, uuid.uuid4().hex + ext)
                try:
                    shutil.copy(src, dst)
                    self.image_path = dst
                    self._show_img()
                except Exception as e:
                    self.app.toast('复制图片失败：%s' % e)
        try:
            if platform == 'android':
                from plyer import filechooser
                filechooser.open_file(on_selection=on_pick)
            else:
                self._desktop_chooser(on_pick)
        except Exception as e:
            self.app.toast('无法打开文件选择器：%s' % e)

    def _desktop_chooser(self, cb):
        fc = FileChooserListView(path=os.path.expanduser('~'), filters=['*.png', '*.jpg', '*.jpeg', '*.webp'])
        box = BoxLayout(orientation='vertical')
        box.add_widget(fc)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        ok = B('确定', background_color=get_color_from_hex(BLUE), color=(1, 1, 1, 1))
        cc = B('取消')
        row.add_widget(ok)
        row.add_widget(cc)
        box.add_widget(row)
        pop = Popup(title='选择图片', content=box, size_hint=(0.92, 0.92))
        ok.bind(on_release=lambda *a: (cb([fc.selection[0]] if fc.selection else []), pop.dismiss()))
        cc.bind(on_release=lambda *a: pop.dismiss())
        pop.open()

    def clear_image(self):
        self.image_path = ''
        self._show_img()

    def save(self):
        name = self.name_inp.text.strip()
        if not name:
            self.app.toast('请先输入名字')
            return
        mem = {'id': self.mem_id or uuid.uuid4().hex, 'name': name, 'image': self.image_path}
        # 起始日期
        if self.st_solar.state == 'down':
            d = parse_ymd(self.solar_inp.text)
            if not d:
                self.app.toast('阳历日期格式：YYYY-MM-DD，如 1974-08-20')
                return
            mem['start_type'] = 'solar'
            mem['start_solar'] = d.isoformat()
            lun = lunar_of(d)
            mem['start_lunar'] = '%d-%d' % (lun.getMonth(), lun.getDay())
        else:
            try:
                yy = int(self.lunar_year.text.strip())
                lm, ld = parse_md(self.lunar_md.text)
            except Exception:
                self.app.toast('阴历年份和月-日格式不对，如 年份1985、月-日 8-20')
                return
            try:
                s = Lunar.fromYmd(yy, lm, ld).getSolar()
                mem['start_type'] = 'lunar'
                mem['start_solar'] = '%d-%02d-%02d' % (s.getYear(), s.getMonth(), s.getDay())
                mem['start_lunar'] = '%d-%d' % (lm, ld)
            except Exception:
                self.app.toast('农历日期无效，请检查（如 8-20）')
                return
        # 重复
        mem['repeat'] = 'yearly' if self.rp_yearly.state == 'down' else 'once'
        # 提醒
        if self.rm_solar.state == 'down':
            mm, dd = parse_md(self.rm_solar_inp.text)
            if mm < 1 or mm > 12 or dd < 1 or dd > 31:
                self.app.toast('阳历提醒格式：月-日，如 03-03')
                return
            mem['remind'] = 'solar'
            mem['remind_solar'] = '%02d-%02d' % (mm, dd)
            mem['remind_lunar'] = ''
        elif self.rm_lunar.state == 'down':
            lm, ld = parse_md(self.rm_lunar_inp.text)
            if lm < 1 or lm > 12 or ld < 1 or ld > 30:
                self.app.toast('阴历提醒格式：月-日，如 01-15')
                return
            mem['remind'] = 'lunar'
            mem['remind_lunar'] = '%d-%d' % (lm, ld)
            mem['remind_solar'] = ''
        else:
            mem['remind'] = ''
            mem['remind_solar'] = ''
            mem['remind_lunar'] = ''
        # 写入
        data = self.app.data
        found = False
        for i, m in enumerate(data['memorials']):
            if m.get('id') == mem['id']:
                data['memorials'][i] = mem
                found = True
                break
        if not found:
            data['memorials'].append(mem)
        save_data(self.app, data)
        self.app.data = data
        self.app.toast('已保存 ✓')
        self.app.back_from_edit()


# ───────────────────────── 屏幕：节假日列表 ─────────────────────────

class HolidayScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')
        head = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(12), 0])
        head.add_widget(L('节假日', font_size=sp(22), bold=True,
                          color=get_color_from_hex(DARK)))
        root.add_widget(head)
        sv = ScrollView()
        self.list = BoxLayout(orientation='vertical')
        self.list.size_hint_y = None
        self.list.bind(minimum_height=self.list.setter('height'))
        sv.add_widget(self.list)
        root.add_widget(sv, 1)
        root.add_widget(TabBar(self.app, 'holidays'))
        self.refresh()
        self.add_widget(root)

    def refresh(self):
        self.list.clear_widgets()
        t = today()
        items = []  # (名称, 副标题, 目标日期)
        # 法定/传统节假日
        legal = [
            ('元旦', '阳历 1月1日', date(t.year, 1, 1)),
            ('春节', '农历 正月初一', None),
            ('清明节', '二十四节气', None),
            ('劳动节', '阳历 5月1日', date(t.year, 5, 1)),
            ('端午节', '农历 五月初五', None),
            ('中秋节', '农历 八月十五', None),
            ('国庆节', '阳历 10月1日', date(t.year, 10, 1)),
            ('元宵节', '农历 正月十五', None),
            ('七夕节', '农历 七月初七', None),
            ('重阳节', '农历 九月初九', None),
            ('腊八节', '农历 腊月初八', None),
            ('小年', '农历 腊月廿三', None),
        ]
        lunar_legal = {'春节': (1, 1), '端午节': (5, 5), '中秋节': (8, 15),
                       '元宵节': (1, 15), '七夕节': (7, 7), '重阳节': (9, 9),
                       '腊八节': (12, 8), '小年': (12, 23)}
        for name, sub, fixed in legal:
            if fixed:
                if fixed < t:
                    fixed = date(t.year + 1, fixed.month, fixed.day)
                items.append((name, sub, fixed))
            elif name == '清明节':
                jq = jieqi_dates(t.year).get('清明')
                if jq:
                    if jq < t:
                        jq = jieqi_dates(t.year + 1).get('清明')
                    items.append((name, sub, jq))
            else:
                lm, ld = lunar_legal[name]
                d = next_yearly_lunar(lm, ld, t)
                items.append((name, sub, d))
        # 二十四节气
        for jq in JIEQI_LIST:
            d = jieqi_dates(t.year).get(jq)
            if d:
                if d < t:
                    d = jieqi_dates(t.year + 1).get(jq)
                if d:
                    items.append((jq, '二十四节气', d))
        items.sort(key=lambda x: x[2])
        for name, sub, d in items:
            self.list.add_widget(self._row(name, sub, d, t))

    def _row(self, name, sub, d, t):
        row = BoxLayout(size_hint_y=None, height=dp(58), padding=[dp(16), dp(8)])
        with row.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(pos=row.pos, size=row.size)
            Color(0.93, 0.94, 0.95, 1)
            Rectangle(pos=(row.x, row.y), size=(row.width, 1))
        left = BoxLayout(orientation='vertical', spacing=dp(2))
        nm = L(name, font_size=sp(16), bold=True, color=get_color_from_hex(DARK))
        sb = L(sub, font_size=sp(11), color=get_color_from_hex(GRAY))
        left.add_widget(nm)
        left.add_widget(sb)
        row.add_widget(left)
        diff = (d - t).days
        color = RED if diff <= 15 else ORANGE
        if diff == 0:
            txt = '就是今天 🎉'
        elif diff == 1:
            txt = '明天'
        else:
            txt = '还有 %d 天' % diff
        rg = L(txt, font_size=sp(15), bold=True, color=get_color_from_hex(color))
        row.add_widget(rg)
        return row


# ───────────────────────── App 主体 ─────────────────────────

class XingjiApp(App):
    title = '星迹日历'
    icon = 'app_icon.png'

    def build(self):
        self.data = load_data(self)
        self.sm = ScreenManager(transition=SlideTransition(duration=0.25))
        self.main_screen = MainScreen(self, name='main')
        self.year_screen = YearScreen(self, name='year')
        self.cards_screen = CardsScreen(self, name='cards')
        self.edit_screen = EditScreen(self, name='edit')
        self.holiday_screen = HolidayScreen(self, name='holidays')
        for s in (self.main_screen, self.year_screen, self.cards_screen,
                  self.edit_screen, self.holiday_screen):
            self.sm.add_widget(s)
        return self.sm

    def on_start(self):
        self.check_today_remind()
        Clock.schedule_once(lambda *a: self.check_today_remind(), 1)

    # ---- 导航 ----
    def switch_tab(self, key):
        if key == 'main':
            self.main_screen.refresh()
            self.sm.current = 'main'
        elif key == 'cards':
            self.cards_screen.refresh()
            self.sm.current = 'cards'
        elif key == 'holidays':
            self.holiday_screen.refresh()
            self.sm.current = 'holidays'

    def show_year(self, y):
        if self.year_screen.year != y:
            self.year_screen.set_year(y)
        self.sm.current = 'year'

    def back_to_month(self):
        self.sm.current = 'main'

    def year_day_click(self, d):
        self.main_screen.cur_date = d
        self.main_screen.refresh()
        self.sm.current = 'main'

    def open_edit(self, mem_id):
        mem = None
        if mem_id:
            for m in self.data.get('memorials', []):
                if m.get('id') == mem_id:
                    mem = m
                    break
        self.edit_screen.load(mem)
        self.sm.current = 'edit'

    def back_from_edit(self):
        self.sm.current = 'cards' if self.sm.current == 'edit' else self.sm.current
        self.main_screen.refresh()
        self.cards_screen.refresh()
        self.holiday_screen.refresh()
        self.sm.current = 'main'

    def mem_index(self, mem_id):
        for i, m in enumerate(self.data.get('memorials', [])):
            if m.get('id') == mem_id:
                return i
        return None

    def show_day_detail(self, d):
        lun = lunar_of(d)
        parts = ['%d年%d月%d日' % (d.year, d.month, d.day),
                 '农历 %s月%s' % (lun.getMonthInChinese(), lun.getDayInChinese())]
        jq = jieqi_text(d)
        if jq:
            parts.append('节气：%s' % jq)
        sf = solar_festival(d)
        if sf:
            parts.append('节日：%s' % sf)
        lf = lunar_festival(d)
        if lf:
            parts.append('农历节日：%s' % lf)
        pop = Popup(title='%d月%d日' % (d.month, d.day),
                    content=L('\n'.join(parts), font_size=sp(16),
                              halign='center', valign='middle',
                              text_size=(dp(240), None)),
                    size_hint=(0.8, 0.42), title_font='zh')
        pop.open()

    def confirm_delete(self, mem_id, back=False):
        box = BoxLayout(orientation='vertical', spacing=dp(12), padding=[dp(10), dp(10)])
        box.add_widget(L('确定删除这个纪念日吗？', font_size=sp(15)))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        yes = B('删除', background_color=get_color_from_hex('#e74c3c'), color=(1, 1, 1, 1))
        no = B('取消')
        row.add_widget(yes)
        row.add_widget(no)
        box.add_widget(row)
        pop = Popup(title='删除确认', content=box, size_hint=(0.8, 0.35), title_font='zh')

        def do_delete(*a):
            data = self.data
            data['memorials'] = [m for m in data['memorials'] if m.get('id') != mem_id]
            save_data(self, data)
            self.data = data
            pop.dismiss()
            self.toast('已删除')
            self.main_screen.refresh()
            self.cards_screen.refresh()
            self.holiday_screen.refresh()
            if back:
                self.sm.current = 'main'
        yes.bind(on_release=do_delete)
        no.bind(on_release=lambda *a: pop.dismiss())
        pop.open()

    def toast(self, msg):
        pop = Popup(title='提示', content=L(msg, font_size=sp(15)),
                    size_hint=(0.7, 0.25), title_font='zh')
        pop.open()
        from kivy.clock import Clock as _C
        _C.schedule_once(lambda *a: pop.dismiss(), 1.5)

    def check_today_remind(self):
        """今天是否有纪念日/提醒 → 手机弹窗通知"""
        try:
            t = today()
            hits = []
            for m in self.data.get('memorials', []):
                if m.get('repeat') == 'once':
                    if m.get('start_solar', '') == t.isoformat():
                        hits.append(m['name'])
                    continue
                rm = m.get('remind', '')
                if rm == 'solar':
                    mm, dd = parse_md(m.get('remind_solar', '1-1'))
                    if (t.month, t.day) == (mm, dd):
                        hits.append(m['name'])
                elif rm == 'lunar':
                    lm, ld = parse_md(m.get('remind_lunar', '1-1'))
                    lun = lunar_of(t)
                    if (lun.getMonth(), lun.getDay()) == (lm, ld):
                        hits.append(m['name'])
            if hits:
                try:
                    from plyer import notification
                    notification.notify(title='星迹日历',
                                        message='今天是：' + '、'.join(hits) + ' 的纪念日 🎉',
                                        timeout=10)
                except Exception:
                    pass
        except Exception as e:
            print('提醒检查失败:', e)


if __name__ == '__main__':
    XingjiApp().run()
