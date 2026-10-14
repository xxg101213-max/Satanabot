"""Compile a real managed overlay geometry library from trusted template.
Not an injected game ESP; caller must supply camera/entity coordinates and renderer.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from .managed import ManagedError, inspect_managed, available

ALLOWED={'fov','line_tracer','box','skeleton','name'}

SOURCE='''using System;
using System.Collections.Generic;
namespace SatanabeOverlay {
  public readonly record struct Point(float X,float Y);
  public readonly record struct Color(byte R,byte G,byte B) {
    public static Color Hex(string s) {
      if(s.Length!=7||s[0]!='#')throw new ArgumentException("Cor inválida");
      return new Color(Convert.ToByte(s.Substring(1,2),16),Convert.ToByte(s.Substring(3,2),16),Convert.ToByte(s.Substring(5,2),16));
    }
  }
  public record Character(string Name,Point Center,Point Head,float Width,float Height,
                          Dictionary<string,Point> Joints,bool Visible);
  public record Primitive(string Kind,Point A,Point B,string Text,Color Color);
  public class EspOverlay {
    // A host application supplies game state, camera transform, and a renderer.
    public static readonly string SettingsJson = @"__SETTINGS__";
    private readonly Dictionary<string,bool> enabled = new();
    private readonly Dictionary<string,Color> colors = new();
    public EspOverlay(){
      foreach(var item in System.Text.Json.JsonDocument.Parse(SettingsJson).RootElement.GetProperty("controls").EnumerateArray()){
        var k=item.GetProperty("feature").GetString()!;
        enabled[k]=item.GetProperty("enabled").GetBoolean();
        colors[k]=Color.Hex(item.GetProperty("color").GetString()!);
      }
    }
    bool On(string name)=>enabled.TryGetValue(name,out var e)&&e;
    Color Cl(string name)=>colors[name];
    public List<Primitive> Render(float viewportW,float viewportH,IEnumerable<Character> entities) {
      var p=new List<Primitive>();
      if(On("fov"))p.Add(new Primitive("circle",new Point(viewportW/2,viewportH/2),new Point(Math.Min(viewportW,viewportH)*0.2f,0),"",Cl("fov")));
      foreach(var c in entities){
        if(!c.Visible)continue;
        if(On("line_tracer"))p.Add(new Primitive("line",new Point(viewportW/2,viewportH),c.Center,"",Cl("line_tracer")));
        if(On("box"))p.Add(new Primitive("box",new Point(c.Center.X-c.Width/2,c.Center.Y-c.Height/2),new Point(c.Width,c.Height),"",Cl("box")));
        if(On("name"))p.Add(new Primitive("text",c.Head,c.Head,c.Name,Cl("name")));
        if(On("skeleton")){
          string[][] pairs = {new[]{"head","neck"},new[]{"neck","spine"},new[]{"spine","hip"},new[]{"neck","leftArm"},new[]{"neck","rightArm"},new[]{"hip","leftLeg"},new[]{"hip","rightLeg"}};
          foreach(var pair in pairs)if(c.Joints.TryGetValue(pair[0],out var a)&&c.Joints.TryGetValue(pair[1],out var b))p.Add(new Primitive("line",a,b,"",Cl("skeleton")));
        }
      }
      return p;
    }
  }
}
'''
PROJECT='''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><AssemblyName>SatanabeOverlay</AssemblyName><GenerateAssemblyInfo>true</GenerateAssemblyInfo></PropertyGroup></Project>'''

def checked_config(controls:dict)->dict:
    normalized=[]
    for key in ('fov','line_tracer','box','skeleton','name'):
        value=controls.get(key, {'enabled':False,'color':'#FFFFFF'})
        color=value.get('color','#FFFFFF')
        if not isinstance(color,str) or len(color)!=7 or color[0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in color[1:]):
            raise ManagedError('Cor fora do padrão #RRGGBB')
        normalized.append({'feature':key,'enabled':bool(value.get('enabled',False)),'color':color})
    return {'schema_version':1,'controls':normalized,'purpose':'standalone geometry library, not an in-game ESP'}

def source_from_controls(controls:dict) -> str:
    settings=json.dumps(checked_config(controls),ensure_ascii=True,separators=(',',':'))
    return SOURCE.replace('__SETTINGS__',settings.replace('"','""'))

def build_overlay(controls:dict) -> dict:
    config=checked_config(controls)
    code=source_from_controls(controls)
    with TemporaryDirectory(prefix='satanabe-overlay-') as d:
        root=Path(d)
        (root/'SatanabeOverlay.csproj').write_text(PROJECT)
        (root/'Overlay.cs').write_text(code)
        try:
            p=subprocess.run(['dotnet','build',str(root/'SatanabeOverlay.csproj'),'-c','Release','--nologo','-o',str(root/'out')],capture_output=True,text=True,timeout=100,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            return {'success':False,'source':code,'config':config,'error':'SDK .NET não disponível ou build excedeu o tempo'}
        if p.returncode:
            return {'success':False,'source':code,'config':config,'error':(p.stdout+'\n'+p.stderr)[-2500:]}
        binary=(root/'out'/'SatanabeOverlay.dll').read_bytes()
        return {'success':True,'binary':binary,'source':code,'config':config,
                'size':len(binary),'validation':'dotnet build succeeded; NOT game integration tested'}
