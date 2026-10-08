#!/usr/bin/env python3
import os, re, sys, io, zipfile, threading, datetime
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import soundfile as sf
import xrni_to_m8 as conv

BG='#101820'; PANEL='#17222b'; PANEL2='#0d151b'; BORDER='#344550'; FG='#f2f5f7'; MUTED='#b9c3cc'; BLUE='#1688f8'; BLUE2='#0b6fd3'; GREEN='#46df69'; ENTRY='#0e171d'

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('XRNI Multisample Converter')
        self.geometry('1220x760')
        self.minsize(1000,650)
        self.configure(bg=BG)
        self.xrni=tk.StringVar(); self.output=tk.StringVar(); self.layer=tk.IntVar(value=4); self.output_mode=tk.StringVar(value='m8')
        self.xrni_display=tk.StringVar(); self.output_display=tk.StringVar()
        self.xrni.trace_add('write', lambda *_: self._refresh_display_path(self.xrni, self.xrni_display))
        self.output.trace_add('write', lambda *_: self._refresh_display_path(self.output, self.output_display))
        self.mono=tk.BooleanVar(value=False); self.normalize=tk.BooleanVar(value=False)
        self.info={}; self._build_styles(); self._build_ui(); self._ensure_output_folders()

    def _build_styles(self):
        s=ttk.Style(self)
        try: s.theme_use('clam')
        except: pass
        s.configure('Dark.TFrame',background=BG); s.configure('Panel.TFrame',background=PANEL)
        s.configure('Dark.TLabel',background=BG,foreground=FG,font=('Segoe UI',10))
        s.configure('Muted.TLabel',background=BG,foreground=MUTED,font=('Segoe UI',10))
        s.configure('Panel.TLabel',background=PANEL,foreground=FG,font=('Segoe UI',10))
        s.configure('PanelMuted.TLabel',background=PANEL,foreground=MUTED,font=('Segoe UI',9))
        s.configure('Section.TLabel',background=BG,foreground=FG,font=('Segoe UI',12,'bold'))
        s.configure('PanelSection.TLabel',background=PANEL,foreground=FG,font=('Segoe UI',12,'bold'))
        s.configure('Title.TLabel',background=BG,foreground=FG,font=('Segoe UI',28,'bold'))
        s.configure('Subtitle.TLabel',background=BG,foreground=MUTED,font=('Segoe UI',13))
        s.configure('Dark.TEntry',fieldbackground=ENTRY,foreground=FG,insertcolor=FG,bordercolor=BORDER,padding=8)
        s.configure('Dark.TButton',background='#35434d',foreground=FG,padding=(16,9),font=('Segoe UI',10))
        s.map('Dark.TButton',background=[('active','#44545f')])
        s.configure('Blue.TButton',background=BLUE,foreground='white',padding=(18,13),font=('Segoe UI',15,'bold'),borderwidth=0)
        s.map('Blue.TButton',background=[('active',BLUE2),('disabled','#31536d')])
        s.configure('Dark.TRadiobutton',background=PANEL,foreground=FG,font=('Segoe UI',10),indicatorcolor=ENTRY)
        s.map('Dark.TRadiobutton',background=[('active',PANEL)],indicatorcolor=[('selected',BLUE)])
        s.configure('Dark.TCheckbutton',background=PANEL,foreground=FG,font=('Segoe UI',10,'bold'),indicatorcolor=ENTRY)
        s.map('Dark.TCheckbutton',background=[('active',PANEL)],indicatorcolor=[('selected',BLUE)])
        s.configure('Blue.Horizontal.TProgressbar',troughcolor='#24313a',background=GREEN,bordercolor='#24313a',lightcolor=GREEN,darkcolor=GREEN)

    @staticmethod
    def _short_display_path(path):
        """Display only the immediate parent directory and the file name."""
        if not path:
            return ''
        # Split both Windows and POSIX paths, irrespective of the host OS.
        parts = re.split(r'[\\/]+', path.rstrip('\\/'))
        return '/'.join(parts[-2:]) if len(parts) > 1 else parts[0]

    def _refresh_display_path(self, source, destination):
        destination.set(self._short_display_path(source.get()))

    def _box(self,parent):
        return tk.Frame(parent,bg=PANEL,highlightbackground=BORDER,highlightthickness=1,bd=0)

    def _asset_path(self, filename):
        """Return an asset path that works from source and PyInstaller-style bundles."""
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, 'assets', filename)

    def _load_header_images(self):
        """Load bundled header artwork and retain references for Tkinter."""
        self.renoise_header_img = None
        self.m8_header_img = None
        try:
            self.renoise_header_img = tk.PhotoImage(file=self._asset_path('renoise_header.png'))
        except Exception as e:
            self.log_asset_warning = f'Renoise header image could not be loaded: {e}'
        try:
            self.m8_header_img = tk.PhotoImage(file=self._asset_path('m8_header.png'))
        except Exception as e:
            prev = getattr(self, 'log_asset_warning', '')
            self.log_asset_warning = (prev + '\n' if prev else '') + f'M8 header image could not be loaded: {e}'

    def _build_ui(self):
        root=tk.Frame(self,bg=BG); root.pack(fill='both',expand=True,padx=18,pady=14)
        header=tk.Frame(root,bg=BG); header.pack(fill='x',pady=(0,12))
        self._load_header_images()

        if self.renoise_header_img is not None:
            tk.Label(header,image=self.renoise_header_img,bg=BG,bd=0).pack(side='left',padx=(0,16))

        titlebox=tk.Frame(header,bg=BG)
        titlebox.pack(side='left',fill='x',expand=True)
        ttk.Label(titlebox,text='XRNI Multisample Converter',style='Title.TLabel').pack(anchor='w',pady=(8,0))
        ttk.Label(titlebox,text='Convert Renoise instruments for Dirtywave M8 or Expert Sleepers Disting NT',style='Subtitle.TLabel').pack(anchor='w',pady=(2,0))

        if self.m8_header_img is not None:
            tk.Label(header,image=self.m8_header_img,bg=BG,bd=0).pack(side='right',padx=(16,0))

        body=tk.PanedWindow(root,orient='horizontal',bg=BG,sashwidth=8,sashrelief='flat',bd=0)
        body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=BG); right=tk.Frame(body,bg=BG)
        body.add(left,minsize=500,stretch='always'); body.add(right,minsize=420,stretch='always')
        self._build_left(left); self._build_right(right)

    def _build_left(self,p):
        ttk.Label(p,text='1. Select Renoise Instrument (.xrni)',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        row=tk.Frame(p,bg=BG); row.pack(fill='x',pady=(0,12))
        ttk.Entry(row,textvariable=self.xrni_display,style='Dark.TEntry',state='readonly').pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Browse…',style='Dark.TButton',command=self.pick_xrni).pack(side='left',padx=(10,0))

        ttk.Label(p,text='2. Output Format',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        modebox=self._box(p); modebox.pack(fill='x',pady=(0,12))
        mi=tk.Frame(modebox,bg=PANEL); mi.pack(fill='x',padx=14,pady=11)
        ttk.Radiobutton(mi,text='Dirtywave M8 WAV',variable=self.output_mode,value='m8',
                        style='Dark.TRadiobutton',command=self.output_mode_changed).pack(anchor='w',pady=(0,5))
        ntrow=tk.Frame(mi,bg=PANEL); ntrow.pack(fill='x')
        ttk.Radiobutton(ntrow,text='Disting NT Poly Multisample JSON',variable=self.output_mode,value='disting',
                        style='Dark.TRadiobutton',command=self.output_mode_changed).pack(side='left')
        tk.Label(ntrow,text='  DISTING NT ONLY — NOT M8 OUTPUT',bg=PANEL,fg='#ffbf4a',
                 font=('Segoe UI',9,'bold')).pack(side='left',padx=(8,0))
        ttk.Label(mi,text='Disting mode exports all XRNI velocity layers as 16-bit / 44.1 kHz WAVs plus a Poly Multisample preset.',
                  style='PanelMuted.TLabel').pack(anchor='w',padx=(27,0),pady=(3,0))

        self.velocity_title=ttk.Label(p,text='3. Choose M8 Velocity Layer',style='Section.TLabel')
        self.velocity_title.pack(anchor='w',pady=(0,6))
        self.layerbox=self._box(p); self.layerbox.pack(fill='x',pady=(0,12))
        inner=tk.Frame(self.layerbox,bg=PANEL); inner.pack(fill='x',padx=14,pady=11)
        labels=[(1,'1 - Lowest Velocity'),(2,'2 - Second Layer'),(3,'3 - Third Layer'),(4,'4 - Highest Velocity')]
        self.layer_buttons=[]
        for n,label in labels:
            rb=ttk.Radiobutton(inner,text=label,variable=self.layer,value=n,style='Dark.TRadiobutton',command=self.layer_changed)
            rb.pack(side='left',padx=(0,14)); self.layer_buttons.append(rb)

        ttk.Label(p,text='4. Output File',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        row=tk.Frame(p,bg=BG); row.pack(fill='x',pady=(0,12))
        ttk.Entry(row,textvariable=self.output_display,style='Dark.TEntry',state='readonly').pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Browse…',style='Dark.TButton',command=self.pick_output).pack(side='left',padx=(10,0))

        ttk.Label(p,text='5. M8 Options',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        self.opt=self._box(p); self.opt.pack(fill='both',expand=True,pady=(0,10))
        oi=tk.Frame(self.opt,bg=PANEL); oi.pack(fill='both',expand=True,padx=16,pady=10)
        self.norm_widget=self._check_with_help(oi,'Normalize Audio','Scale the complete joined M8 instrument to maximum peak level without changing relative note levels.',self.normalize)
        self.norm_widget.pack(fill='x',pady=(0,8))
        self.cue_widget=tk.Frame(oi,bg=PANEL); self.cue_widget.pack(fill='x',pady=(0,8))
        ttk.Checkbutton(self.cue_widget,text='Embed CUE Markers',style='Dark.TCheckbutton',state='disabled').pack(anchor='w')
        ttk.Label(self.cue_widget,text='Always enabled for M8 WAV output.',style='PanelMuted.TLabel').pack(anchor='w',padx=(27,0),pady=(2,0))
        self.mono_widget=self._check_with_help(oi,'Convert to Mono','Downmix the M8 WAV to mono to reduce file size.',self.mono)
        self.mono_widget.pack(fill='x')

        self.go=ttk.Button(p,text='↻   Convert to M8 WAV',style='Blue.TButton',command=self.start)
        self.go.pack(fill='x',ipady=3)
        self.output_mode_changed()

    def _check_with_help(self,parent,title,helptext,var):
        f=tk.Frame(parent,bg=PANEL)
        ttk.Checkbutton(f,text=title,variable=var,style='Dark.TCheckbutton').pack(anchor='w')
        ttk.Label(f,text=helptext,style='PanelMuted.TLabel',wraplength=500).pack(anchor='w',padx=(27,0),pady=(2,0))
        return f

    def _build_right(self,p):
        ttk.Label(p,text='Instrument Information',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        info=self._box(p); info.pack(fill='x',pady=(0,12))
        self.info_label=tk.Label(info,text='Select an XRNI file to inspect its mappings.',justify='left',anchor='nw',bg=PANEL,fg=FG,font=('Consolas',10),padx=14,pady=12)
        self.info_label.pack(fill='x')

        ttk.Label(p,text='Preview of Selected Layer',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        preview=self._box(p); preview.pack(fill='x',pady=(0,12))
        self.keyboard=tk.Canvas(preview,height=112,bg=PANEL2,highlightthickness=0)
        self.keyboard.pack(fill='x',padx=10,pady=(10,4)); self.keyboard.bind('<Configure>',lambda e:self.draw_keyboard())
        self.preview_label=tk.Label(preview,text='No layer selected',justify='left',anchor='w',bg=PANEL,fg=MUTED,font=('Segoe UI',10),padx=12,pady=8)
        self.preview_label.pack(fill='x')

        ttk.Label(p,text='Conversion Log',style='Section.TLabel').pack(anchor='w',pady=(0,6))
        logbox=self._box(p); logbox.pack(fill='both',expand=True)
        self.log=tk.Text(logbox,bg=PANEL2,fg='#d9e1e6',insertbackground=FG,relief='flat',font=('Consolas',9),height=9,wrap='word',state='disabled')
        self.log.pack(fill='both',expand=True,padx=8,pady=(8,4))
        self.log.tag_config('good',foreground=GREEN); self.log.tag_config('bad',foreground='#ff6b6b'); self.log.tag_config('muted',foreground=MUTED)
        self.bar=ttk.Progressbar(logbox,mode='indeterminate',style='Blue.Horizontal.TProgressbar')
        self.bar.pack(fill='x',padx=8,pady=(4,8))

    def logline(self,msg,tag=None):
        stamp=datetime.datetime.now().strftime('%H:%M:%S')
        self.log.config(state='normal'); self.log.insert('end',f'[{stamp}]  {msg}\n',tag or '')
        self.log.see('end'); self.log.config(state='disabled')

    def _safe_note_name(self, midi_note):
        """Filename-safe note name, e.g. C#3 -> Cs3."""
        return conv.midi_name(midi_note).replace('#','s').replace('♯','s')

    def _mapped_output_name(self, source_path=None, requested_path=None):
        """Build an output filename containing layer, note range and slice count."""
        source_path = source_path or self.xrni.get().strip()
        if not source_path:
            return requested_path or ''

        try:
            z, items = conv.parse_xrni(source_path, self.layer.get())
            z.close()
            if not items:
                raise ValueError('No mapped samples in selected velocity layer')
            lo, hi = items[0]['base'], items[-1]['base']
            suffix = f'_M8_L{self.layer.get()}_{self._safe_note_name(lo)}-{self._safe_note_name(hi)}_{len(items)}slices'
        except Exception:
            # Until the XRNI can be parsed, retain the old layer-only fallback.
            suffix = f'_M8_L{self.layer.get()}'

        if requested_path:
            folder = os.path.dirname(requested_path)
            stem = os.path.splitext(os.path.basename(requested_path))[0]
            # Remove a suffix previously generated by this app so it does not accumulate.
            stem = re.sub(r'_M8_L[1-4](?:_[A-G](?:s)?-?\d+-[A-G](?:s)?-?\d+_\d+slices)?$', '', stem, flags=re.I)
            if not stem:
                stem = os.path.splitext(os.path.basename(source_path))[0]
            return os.path.join(folder, stem + suffix + '.wav')

        folder = self._converted_dir('m8')
        stem = os.path.splitext(os.path.basename(source_path))[0]
        return os.path.join(folder, stem + suffix + '.wav')

    def _app_base_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    def _converted_dir(self, mode=None):
        sub = 'Disting NT' if (mode or self.output_mode.get()) == 'disting' else 'M8'
        folder = os.path.join(self._app_base_dir(), 'Converted', sub)
        os.makedirs(folder, exist_ok=True)
        return folder

    def _ensure_output_folders(self):
        os.makedirs(os.path.join(self._app_base_dir(), 'Converted'), exist_ok=True)
        self._converted_dir('m8'); self._converted_dir('disting')

    def _disting_output_name(self, source_path=None, requested_path=None):
        source_path=source_path or self.xrni.get().strip()
        if requested_path:
            folder=os.path.dirname(requested_path); stem=os.path.splitext(os.path.basename(requested_path))[0]
        else:
            folder=self._converted_dir('disting')
            stem=os.path.splitext(os.path.basename(source_path))[0] if source_path else 'Poly_Multisample'
        # Disting NT is the output type, not a part of the preset's name.
        stem=re.sub(r'_DistingNT$','',stem,flags=re.I)
        return os.path.join(folder,stem+'.json')

    def output_mode_changed(self):
        is_nt=self.output_mode.get()=='disting'
        for rb in getattr(self,'layer_buttons',[]):
            rb.configure(state='disabled' if is_nt else 'normal')
        if hasattr(self,'velocity_title'):
            self.velocity_title.configure(text='3. Velocity Layers — ALL layers retained for Disting NT' if is_nt else '3. Choose M8 Velocity Layer')
        if hasattr(self,'go'):
            self.go.configure(text='↻   Convert to Disting NT JSON + Samples' if is_nt else '↻   Convert to M8 WAV')
        if self.xrni.get():
            self.output.set(self._disting_output_name() if is_nt else self._mapped_output_name())
        if self.info:
            if is_nt:
                lo=min(self.info.get('notes',[0])); hi=max(self.info.get('notes',[0]))
                self.preview_label.config(text=f'Notes: {lo} - {hi}     Velocity Layers: ALL ({self.info.get("layers",0)})     Output: Disting NT Poly Multisample')
            else:
                self.layer_changed()

    def pick_xrni(self):
        p=filedialog.askopenfilename(title='Select Renoise instrument',filetypes=[('Renoise instrument','*.xrni'),('All files','*.*')])
        if p:
            self.xrni.set(p)
            self.inspect(p)
            self.output.set(self._disting_output_name(p) if self.output_mode.get()=='disting' else self._mapped_output_name(p))

    def pick_output(self):
        if self.output_mode.get()=='disting':
            p=filedialog.asksaveasfilename(title='Save Disting NT preset',defaultextension='.json',filetypes=[('Disting NT preset','*.json'),('JSON file','*.json')])
            if p:self.output.set(self._disting_output_name(requested_path=p))
        else:
            p=filedialog.asksaveasfilename(title='Save M8 WAV',defaultextension='.wav',filetypes=[('WAV file','*.wav')])
            if p:self.output.set(self._mapped_output_name(requested_path=p))

    def inspect(self,path):
        try:
            with zipfile.ZipFile(path) as z:
                xmlname=next(n for n in z.namelist() if n.lower().endswith('instrument.xml'))
                root=ET.fromstring(z.read(xmlname)); samples=root.findall('.//Samples/Sample')
                notes=[]; vel=set(); mapped=0
                for s in samples:
                    m=s.find('Mapping')
                    if m is None or conv.txt(m,'Layer','')!='Note-On Layer': continue
                    try: base=int(conv.txt(m,'BaseNote')); vs=int(conv.txt(m,'VelocityStart','0')); ve=int(conv.txt(m,'VelocityEnd','127'))
                    except: continue
                    notes.append(base); vel.add((vs,ve)); mapped+=1
                audio=sorted([n for n in z.namelist() if n.lower().endswith(conv.AUDIO_EXTS)])
                sr=ch=subtype='?'
                if audio:
                    data=z.read(audio[0]); inf=sf.info(io.BytesIO(data)); sr=inf.samplerate; ch=inf.channels; subtype=inf.subtype
                uniq=sorted(set(notes)); layer_count=max((sum(1 for s in samples if (lambda m: m is not None and conv.txt(m,'Layer','')=='Note-On Layer' and conv.txt(m,'BaseNote','')==str(n))(s.find('Mapping'))) for n in uniq),default=0)
                self.info={'total':len(samples),'mapped':mapped,'notes':uniq,'layers':layer_count,'sr':sr,'ch':ch,'subtype':subtype}
                rng=f'{min(uniq)} - {max(uniq)}  ({len(uniq)} notes)' if uniq else '—'
                chans='Stereo' if ch==2 else ('Mono' if ch==1 else f'{ch} channels')
                self.info_label.config(text=f'Instrument:      {os.path.basename(path)}\nTotal Samples:   {len(samples)}\nMapped Notes:    {rng}\nVelocity Layers: {layer_count}\nSample Format:   {sr/1000:g} kHz, {chans}, {subtype}')
                self.logline(f'Loaded instrument: {os.path.basename(path)}')
                self.logline(f'Found {len(samples)} samples and {layer_count} velocity layer(s).','muted')
                self.layer_changed(); self.draw_keyboard()
        except Exception as e:
            self.info={}; self.info_label.config(text=f'Could not inspect instrument:\n{e}'); self.logline(str(e),'bad')

    def layer_changed(self):
        if self.output_mode.get()=='disting':
            if self.xrni.get(): self.output.set(self._disting_output_name())
            return
        if self.xrni.get(): self.output.set(self._mapped_output_name())
        if not self.info: return
        try:
            z,items=conv.parse_xrni(self.xrni.get(),self.layer.get()); z.close()
            lo,hi=items[0]['base'],items[-1]['base']; vr=f'{items[0]["vstart"]} - {items[0]["vend"]}'
            ch='mono' if self.mono.get() else ('stereo' if self.info.get('ch')==2 else 'mono')
            self.preview_label.config(text=f'Notes:  {lo} - {hi}  ({len(items)} samples)     Velocity Range: {vr}     Output: {len(items)} {ch} slices')
        except Exception as e: self.preview_label.config(text=str(e))
        self.draw_keyboard()

    def draw_keyboard(self):
        c=self.keyboard; c.delete('all'); w=max(c.winfo_width(),300); h=max(c.winfo_height(),108)
        start,end=12,120; white_notes=[n for n in range(start,end+1) if n%12 in (0,2,4,5,7,9,11)]
        side_pad=14
        usable_w=max(w-(side_pad*2),1)
        ww=usable_w/len(white_notes); selected=set(self.info.get('notes',[])) if self.info else set()
        xpos={}; x=side_pad

        # Dedicated octave-label row, then a separator/spacer before the keys.
        label_y=8
        separator_y=25
        key_top=34
        key_bottom=h-8

        for n in white_notes:
            xpos[n]=x
            fill='#5aaef9' if n in selected else '#edf1f3'
            c.create_rectangle(x,key_top,x+ww,key_bottom,fill=fill,outline='#1b252c')
            x+=ww

        # Black keys positioned after preceding white key.
        for n in range(start,end+1):
            if n%12 not in (1,3,6,8,10): continue
            prev=n-1
            if prev in xpos:
                bx=xpos[prev]+ww*0.68
                fill='#177bd0' if n in selected else '#182128'
                c.create_rectangle(bx,key_top,bx+ww*.62,key_top+(key_bottom-key_top)*.60,
                                   fill=fill,outline='#0a0f13')

        # Octave labels live above the spacer line, not on top of the piano.
        for octv in range(0,10):
            n=(octv+1)*12
            if n in xpos:
                c.create_text(xpos[n]+ww*.5,label_y,text=f'C{octv}',fill=MUTED,
                              anchor='n',font=('Segoe UI',8,'bold'))

        # Visible spacer/separator line between labels and keys.
        c.create_line(side_pad,separator_y,w-side_pad,separator_y,fill=BORDER,width=1)

    def start(self):
        src=self.xrni.get().strip(); out=self.output.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror('XRNI Converter','Please select a valid .xrni file.'); return

        if self.output_mode.get()=='disting':
            out=self._disting_output_name(src,out if out else None); self.output.set(out)
            self.go.config(state='disabled'); self.bar.start(10)
            self.logline('Disting NT mode: keeping ALL velocity layers…')
            threading.Thread(target=self.convert_disting,args=(src,out),daemon=True).start()
            return

        out=self._mapped_output_name(src,out if out else None); self.output.set(out)
        self.go.config(state='disabled'); self.bar.start(10); self.logline(f'Selecting velocity layer {self.layer.get()}…')
        threading.Thread(target=self.convert,args=(src,out,self.layer.get(),self.mono.get(),self.normalize.get()),daemon=True).start()

    def convert_disting(self,src,out):
        try:
            template=self._asset_path('disting_nt_poly_multisample_template.json')
            result=conv.write_disting_nt_bundle(src,out,template_path=template,
                                                progress=lambda m:self.after(0,self.logline,m))
            self.after(0,self.done_disting,result)
        except Exception as e:
            self.after(0,self.failed,str(e))

    def done_disting(self,result):
        self.bar.stop(); self.go.config(state='normal')
        self.output.set(result['json'])
        lo=conv.midi_name(result['lo']); hi=conv.midi_name(result['hi'])
        self.logline(f'Done! Disting NT preset: {result["sample_count"]} samples, {result["layers"]} velocity layer(s), {lo}–{hi}.','good')
        self.logline(f'Preset: {result["json"]}','good')
        self.logline(f'Samples: {result["samples_dir"]}','good')
        messagebox.showinfo('Disting NT conversion complete',
                            f'Disting NT preset created:\\n{result["json"]}\\n\\n'
                            f'Poly Multisample WAV folder:\\n{result["samples_dir"]}\\n\\n'
                            f'Copy the JSON preset and the generated samples folder to the Disting NT MicroSD card.')

    def convert(self,src,out,layer,mono,normalize):
        try:
            z,items=conv.parse_xrni(src,layer); arrays=[]; sr=None
            try:
                self.after(0,self.logline,f'Processing {len(items)} mapped notes…')
                for it in items:
                    a,s=conv.decode(z,it)
                    if sr is None: sr=s
                    if s!=sr: raise ValueError(f'Mixed sample rates are not supported ({s} vs {sr})')
                    if mono: a=a.mean(axis=1,keepdims=True)
                    if arrays and a.shape[1]!=arrays[0].shape[1]: raise ValueError('Mixed channel counts are not supported')
                    arrays.append(a)
                if normalize and arrays:
                    self.after(0,self.logline,'Normalizing joined instrument…')
                    peak=max(float(abs(a).max()) for a in arrays if a.size)
                    if peak>0: arrays=[a/peak for a in arrays]
            finally: z.close()
            lo,hi=items[0]['base'],items[-1]['base']; labels=[f'{i+1:03d}_{conv.midi_name(it["base"])}' for i,it in enumerate(items)]
            self.after(0,self.logline,'Writing WAV and CUE markers…')
            starts,total=conv.write_m8_wav(out,arrays,sr,labels)
            mapfile=os.path.splitext(out)[0]+'_map.txt'
            with open(mapfile,'w',encoding='utf8') as f:
                f.write(f'XRNI: {os.path.basename(src)}\nWAV: {os.path.basename(out)}\nSample rate: {sr}\nChannels: {arrays[0].shape[1]}\nSlices: {len(items)}\nRange: {conv.midi_name(lo)} (MIDI {lo}) to {conv.midi_name(hi)} (MIDI {hi})\nVelocity layer: {layer} (1=lowest)\nNormalized: {"Yes" if normalize else "No"}\n\n')
                f.write('slice\tmidi\tnote\tvelocity\tstart_frame\tsource\n')
                for n,(it,pos) in enumerate(zip(items,starts),1): f.write(f'{n}\t{it["base"]}\t{conv.midi_name(it["base"])}\t{it["vstart"]}-{it["vend"]}\t{pos}\t{it["archive"]}\n')
            self.after(0,self.done,out,mapfile,len(items),lo,hi,sr,arrays[0].shape[1])
        except Exception as e: self.after(0,self.failed,str(e))

    def done(self,out,mapfile,count,lo,hi,sr,ch):
        self.bar.stop(); self.go.config(state='normal'); self.logline(f'Done! {count} slices, {conv.midi_name(lo)}–{conv.midi_name(hi)}, {sr} Hz, {ch} channel(s).','good'); self.logline(f'Output: {out}','good')
        messagebox.showinfo('Conversion complete',f'M8 WAV created:\n{out}\n\nSlice map:\n{mapfile}')
    def failed(self,msg):
        self.bar.stop(); self.go.config(state='normal'); self.logline(f'Conversion failed: {msg}','bad'); messagebox.showerror('Conversion failed',msg)

if __name__=='__main__': App().mainloop()
