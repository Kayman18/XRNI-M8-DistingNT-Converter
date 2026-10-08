#!/usr/bin/env python3
"""Convert a Renoise XRNI multisampled instrument to one Dirtywave M8 sliced WAV.
Selects a requested velocity layer (1=lowest, 4=highest) for each BaseNote and embeds CUE markers.
Requires: pip install numpy soundfile
"""
import argparse, io, os, re, struct, zipfile, json, shutil
import xml.etree.ElementTree as ET
import numpy as np
import soundfile as sf

AUDIO_EXTS=(".wav",".flac",".aif",".aiff")

def txt(e,n,d=None):
    x=e.find(n); return x.text.strip() if x is not None and x.text else d

def midi_name(n):
    names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    return f"{names[n%12]}{n//12-1}"

def parse_xrni(path, layer):
    z=zipfile.ZipFile(path)
    xmlname=next((n for n in z.namelist() if n.lower().endswith('instrument.xml')),None)
    if not xmlname: raise ValueError('Instrument.xml not found')
    root=ET.fromstring(z.read(xmlname))
    samples=root.findall('.//Samples/Sample')
    audio=sorted([n for n in z.namelist() if n.lower().endswith(AUDIO_EXTS)], key=lambda s: int(re.search(r'Sample(\d+)',s).group(1)) if re.search(r'Sample(\d+)',s) else 999999)
    candidates=[]
    for i,s in enumerate(samples):
        m=s.find('Mapping')
        if m is None or txt(m,'Layer','')!='Note-On Layer' or i>=len(audio): continue
        try:
            base=int(txt(m,'BaseNote')); vs=int(txt(m,'VelocityStart','0')); ve=int(txt(m,'VelocityEnd','127'))
        except ValueError: continue
        candidates.append(dict(index=i,base=base,vstart=vs,vend=ve,name=txt(s,'Name',f'Sample{i}'),archive=audio[i]))
    if not candidates: raise ValueError('No mapped Note-On samples found')

    by_note={}
    for c in candidates:
        by_note.setdefault(c['base'], []).append(c)
    selected=[]
    missing=[]
    for base in sorted(by_note):
        layers=sorted(by_note[base], key=lambda c: (c['vstart'], c['vend']))
        if layer > len(layers):
            missing.append((base,len(layers)))
        else:
            selected.append(layers[layer-1])
    if missing:
        details=', '.join(f'{midi_name(n)} has {count}' for n,count in missing[:8])
        if len(missing)>8: details += f', and {len(missing)-8} more'
        raise ValueError(f'Velocity layer {layer} is unavailable: {details}. Choose a lower layer number.')
    return z,selected

def decode(z, item):
    data=z.read(item['archive'])
    a,sr=sf.read(io.BytesIO(data),dtype='float32',always_2d=True)
    return a,sr

def pcm16(a):
    return np.clip(np.rint(np.clip(a,-1,1)*32767),-32768,32767).astype('<i2').tobytes()

def chunk(tag,data):
    return tag+struct.pack('<I',len(data))+data+(b'\0' if len(data)&1 else b'')

def write_m8_wav(path, arrays, sr, labels):
    ch=arrays[0].shape[1]; starts=[]; pos=0; pcm=[]
    for a in arrays:
        starts.append(pos); pos+=len(a); pcm.append(pcm16(a))
    fmt=struct.pack('<HHIIHH',1,ch,sr,sr*ch*2,ch*2,16)
    # Labels first (M8-safe ordering used by current conversion tools)
    adtl=b''
    for i,label in enumerate(labels,1):
        payload=struct.pack('<I',i)+label.encode('ascii','replace')+b'\0'
        adtl+=chunk(b'labl',payload)
    listdata=b'adtl'+adtl
    cues=struct.pack('<I',len(starts))
    for i,p in enumerate(starts,1):
        cues+=struct.pack('<IIIIII',i,p,0x61746164,0,0,p)  # 'data' little endian
    body=chunk(b'fmt ',fmt)+chunk(b'LIST',listdata)+chunk(b'data',b''.join(pcm))+chunk(b'cue ',cues)
    with open(path,'wb') as f: f.write(b'RIFF'+struct.pack('<I',len(body)+4)+b'WAVE'+body)
    return starts,pos


def parse_all_xrni(path):
    """Return all mapped Note-On samples, preserving every velocity layer."""
    z=zipfile.ZipFile(path)
    xmlname=next((n for n in z.namelist() if n.lower().endswith('instrument.xml')),None)
    if not xmlname:
        z.close()
        raise ValueError('Instrument.xml not found')
    root=ET.fromstring(z.read(xmlname))
    samples=root.findall('.//Samples/Sample')
    audio=sorted([n for n in z.namelist() if n.lower().endswith(AUDIO_EXTS)],
                 key=lambda s: int(re.search(r'Sample(\d+)',s).group(1))
                 if re.search(r'Sample(\d+)',s) else 999999)
    items=[]
    for i,s in enumerate(samples):
        m=s.find('Mapping')
        if m is None or txt(m,'Layer','')!='Note-On Layer' or i>=len(audio):
            continue
        try:
            base=int(txt(m,'BaseNote'))
            vs=int(txt(m,'VelocityStart','0'))
            ve=int(txt(m,'VelocityEnd','127'))
        except (ValueError, TypeError):
            continue
        items.append(dict(index=i,base=base,vstart=vs,vend=ve,
                          name=txt(s,'Name',f'Sample{i}'),archive=audio[i]))
    if not items:
        z.close()
        raise ValueError('No mapped Note-On samples found')
    by_note={}
    for item in items:
        by_note.setdefault(item['base'],[]).append(item)
    ordered=[]
    for base in sorted(by_note):
        layers=sorted(by_note[base],key=lambda x:(x['vstart'],x['vend']))
        for layer_no,item in enumerate(layers,1):
            item=dict(item)
            item['velocity_layer']=layer_no
            item['velocity_layers_for_note']=len(layers)
            ordered.append(item)
    return z,ordered

def safe_filename(text):
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',text).strip().strip('.')
    return text or 'XRNI_Instrument'

def resample_audio_linear(audio, source_rate, target_rate=44100):
    """Resample mono/stereo NumPy audio to target_rate with linear interpolation."""
    if int(source_rate) == int(target_rate):
        return audio
    if source_rate <= 0:
        raise ValueError('Invalid source sample rate')
    frames = len(audio)
    if frames < 2:
        return audio
    new_frames = max(1, int(round(frames * float(target_rate) / float(source_rate))))
    old_x = np.linspace(0.0, 1.0, frames, endpoint=True)
    new_x = np.linspace(0.0, 1.0, new_frames, endpoint=True)
    if audio.ndim == 1:
        return np.interp(new_x, old_x, audio).astype(np.float32)
    channels = [np.interp(new_x, old_x, audio[:, ch]) for ch in range(audio.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)

def write_disting_nt_bundle(xrni_path, json_path, template_path=None, progress=None):
    """Create a Disting NT Poly Multisample preset plus its samples folder."""
    z,items=parse_all_xrni(xrni_path)
    try:
        preset_stem=safe_filename(os.path.splitext(os.path.basename(json_path))[0])
        # The NT preset refers to a folder inside the SD card's root samples folder.
        sample_folder_name=safe_filename(os.path.splitext(os.path.basename(xrni_path))[0])
        output_root=os.path.dirname(os.path.abspath(json_path))
        instrument_dir=os.path.join(output_root,sample_folder_name)
        os.makedirs(instrument_dir,exist_ok=True)
        json_path=os.path.join(instrument_dir,os.path.basename(json_path))
        samples_root=os.path.join(instrument_dir,'samples')
        sample_dir=os.path.join(samples_root,sample_folder_name)
        os.makedirs(sample_dir,exist_ok=True)

        # Remove only WAVs previously generated by this converter in this exact folder.
        for fn in os.listdir(sample_dir):
            if fn.lower().endswith('.wav') and re.search(r'_V\d+\.wav$',fn,re.I):
                try: os.remove(os.path.join(sample_dir,fn))
                except OSError: pass

        if progress:
            progress(f'Exporting {len(items)} Disting NT multisamples (all velocity layers)…')

        written=[]
        for idx,it in enumerate(items,1):
            a,sr=decode(z,it)
            note=midi_name(it['base'])
            # Expert Sleepers naming: natural note plus _V1, _V2... from low to high velocity.
            filename=f'{sample_folder_name}_{note}_V{it["velocity_layer"]}.wav'
            dest=os.path.join(sample_dir,filename)
            a=resample_audio_linear(a,sr,44100)
            sf.write(dest,a,44100,format='WAV',subtype='PCM_16')
            written.append((it,dest))
            if progress and (idx==1 or idx==len(items) or idx%25==0):
                progress(f'Exported {idx}/{len(items)} samples…')
    finally:
        z.close()

    if template_path and os.path.isfile(template_path):
        with open(template_path,'r',encoding='utf-8') as f:
            preset=json.load(f)
    else:
        preset={
            "kind":"disting NT preset","version":1,"author":"",
            "name":"Poly Multisample","slots":[{
                "guid":"pyms","specs":[1,8,0],
                "timbres":[{"folder":sample_folder_name}],
                "name":"Poly Multisample",
                "parameters":[[2,0,0,0,-1,0,48,13081,0,0],
                              [0,0,1,13,14,0,0,1,1,0,0,60,100,77,100,0,0,0,0,0,0,1,1,1,1,1,1,1,2,0,0,1,1,0,0,1,0,3,0,0,1,0,0,0,0]],
                "ui":{"page":2,"items":[0,0,0,0,0,0],"display":"params"}}],
            "ui":{"currentSlot":0,"displayMode":"algorithm"}
        }

    preset["kind"]="disting NT preset"
    preset["version"]=1
    preset["name"]=(preset_stem[:20]).ljust(20)
    slots=preset.setdefault("slots",[])
    pyms=next((s for s in slots if s.get("guid")=="pyms"),None)
    if pyms is None:
        raise ValueError('The Disting NT template does not contain a Poly Multisample (pyms) slot')
    pyms["name"]="Poly Multisample".ljust(23)
    pyms["timbres"]=[{"folder":sample_folder_name}]

    with open(json_path,'w',encoding='utf-8',newline='\n') as f:
        json.dump(preset,f,indent=1,ensure_ascii=False)
        f.write('\n')

    notes=sorted(set(i['base'] for i in items))
    layers=max(i['velocity_layer'] for i in items)
    return {
        "json":json_path,
        "samples_dir":sample_dir,
        "sample_folder":sample_folder_name,
        "sample_count":len(items),
        "note_count":len(notes),
        "lo":min(notes),
        "hi":max(notes),
        "layers":layers
    }

def main():
    ap=argparse.ArgumentParser(description='XRNI -> Dirtywave M8 selectable-velocity multisample WAV')
    ap.add_argument('xrni'); ap.add_argument('output',nargs='?')
    ap.add_argument('layer', nargs='?', type=int, choices=range(1,5), default=4, help='velocity layer: 1=lowest, 2=second, 3=third, 4=highest (default: 4)')
    ap.add_argument('--mono',action='store_true',help='downmix to mono')
    ap.add_argument('--normalize',action='store_true',help='normalize joined output peak to 0 dBFS')
    args=ap.parse_args()
    z,items=parse_xrni(args.xrni,args.layer)
    arrays=[]; sr=None
    for it in items:
        a,s=decode(z,it)
        if sr is None: sr=s
        if s!=sr: raise ValueError(f'Mixed sample rates are not supported ({s} vs {sr})')
        if args.mono: a=a.mean(axis=1,keepdims=True)
        if arrays and a.shape[1]!=arrays[0].shape[1]: raise ValueError('Mixed channel counts are not supported')
        arrays.append(a)
    z.close()
    if args.normalize and arrays:
        peak=max(float(abs(a).max()) for a in arrays if a.size)
        if peak > 0:
            arrays=[a/peak for a in arrays]
    lo,hi=items[0]['base'],items[-1]['base']
    out=args.output or os.path.splitext(args.xrni)[0]+f'_M8_L{args.layer}_{midi_name(lo)}-{midi_name(hi)}-{len(items)}.wav'
    labels=[f"{i+1:03d}_{midi_name(it['base'])}" for i,it in enumerate(items)]
    starts,total=write_m8_wav(out,arrays,sr,labels)
    mapfile=os.path.splitext(out)[0]+'_map.txt'
    with open(mapfile,'w',encoding='utf8') as f:
        f.write(f'XRNI: {os.path.basename(args.xrni)}\nWAV: {os.path.basename(out)}\nSample rate: {sr}\nChannels: {arrays[0].shape[1]}\nSlices: {len(items)}\nRange: {midi_name(lo)} (MIDI {lo}) to {midi_name(hi)} (MIDI {hi})\nVelocity layer: {args.layer} (1=lowest, 4=highest)\nNormalized: {'Yes' if args.normalize else 'No'}\n\n')
        f.write('slice\tmidi\tnote\tvelocity\tstart_frame\tsource\n')
        for n,(it,p) in enumerate(zip(items,starts),1): f.write(f"{n}\t{it['base']}\t{midi_name(it['base'])}\t{it['vstart']}-{it['vend']}\t{p}\t{it['archive']}\n")
    print(f'Wrote {out}')
    print(f'Wrote {mapfile}')
    print(f'Layer {args.layer}: {len(items)} slices, {midi_name(lo)}-{midi_name(hi)}, {sr} Hz, {arrays[0].shape[1]} channel(s)')
if __name__=='__main__': main()
