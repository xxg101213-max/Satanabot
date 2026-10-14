using System.Text.Json;
using System.Security.Cryptography;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Sandbox-oriented managed assembly tool. Does not edit native IL2CPP or attach to a process.
static class Worker {
  static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> ts) => ts.SelectMany(t => new[]{t}.Concat(AllTypes(t.NestedTypes)));
  static string Id(MethodDefinition m) => $"{m.DeclaringType.FullName}::{m.Name}({string.Join(",", m.Parameters.Select(p=>p.ParameterType.FullName))}):{m.ReturnType.FullName}";
  static bool IsLiteral(Instruction i) => i.OpCode.Code switch {
     Code.Ldstr or Code.Ldc_I4 or Code.Ldc_I4_S or Code.Ldc_I4_0 or Code.Ldc_I4_1 or Code.Ldc_I4_2 or Code.Ldc_I4_3 or Code.Ldc_I4_4 or Code.Ldc_I4_5 or Code.Ldc_I4_6 or Code.Ldc_I4_7 or Code.Ldc_I4_8 or Code.Ldc_I4_M1 or Code.Ldc_R4 or Code.Ldc_R8 => true,
     _ => false
  };
  static object? Value(Instruction i) => i.OpCode.Code switch {
    Code.Ldc_I4_M1 => -1, Code.Ldc_I4_0 => 0, Code.Ldc_I4_1 => 1,
    Code.Ldc_I4_2 => 2, Code.Ldc_I4_3 => 3, Code.Ldc_I4_4 => 4,
    Code.Ldc_I4_5 => 5, Code.Ldc_I4_6 => 6, Code.Ldc_I4_7 => 7, Code.Ldc_I4_8 => 8,
    Code.Ldc_I4_S => Convert.ToInt32(i.Operand), Code.Ldc_I4 => i.Operand,
    Code.Ldc_R4 or Code.Ldc_R8 or Code.Ldstr => i.Operand, _ => null
  };
  static string Shape(Instruction i) => IsLiteral(i) ? "literal:"+(Value(i) is string ? "str" : Value(i) is float ? "f32" : Value(i) is double ? "f64" : "int") : i.OpCode.Name;
  static void SetValue(Instruction i, object? value){
    // Normalize integer opcodes to Ldc_I4; this preserves stack behavior.
    if (value is string s){i.OpCode=OpCodes.Ldstr; i.Operand=s;}
    else if(value is float f){i.OpCode=OpCodes.Ldc_R4; i.Operand=f;}
    else if(value is double d){i.OpCode=OpCodes.Ldc_R8; i.Operand=d;}
    else if(value is int n){i.OpCode=OpCodes.Ldc_I4; i.Operand=n;}
    else throw new InvalidOperationException("Literal não suportado");
  }
  static AssemblyDefinition Read(string p)=>AssemblyDefinition.ReadAssembly(p,new ReaderParameters {InMemory = true, ReadSymbols = false });
  static Dictionary<string,MethodDefinition> Methods(AssemblyDefinition a)=>AllTypes(a.MainModule.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).GroupBy(Id).Where(g=>g.Count()==1).ToDictionary(g=>g.Key,g=>g.First());
  static object Inspect(AssemblyDefinition assembly){var m=Methods(assembly);return new { assembly=assembly.Name.Name, types=AllTypes(assembly.MainModule.Types).Count(), methods=m.Count, sample=m.Keys.Take(60).ToArray() };}
  static object Transfer(string baseline,string modified,string newer,string output){
    using var a=Read(baseline); using var b=Read(modified);using var c=Read(newer);
    var before=Methods(a); var old=Methods(b);var target=Methods(c);
    int applied=0;var notes=new List<string>();
    foreach(var entry in before){
      if(!old.TryGetValue(entry.Key,out var changed)||!target.TryGetValue(entry.Key,out var now))continue;
      var original=entry.Value.Body.Instructions;var changedIL=changed.Body.Instructions;var newIL=now.Body.Instructions;
      if(original.Count!=changedIL.Count||original.Count!=newIL.Count) {notes.Add($"{entry.Key}: tamanho de IL mudou; ignorado");continue;}
      // Require same instruction skeleton in both versions. Never remap branches, calls or tokens.
      if(!original.Select(Shape).SequenceEqual(changedIL.Select(Shape))||!original.Select(Shape).SequenceEqual(newIL.Select(Shape))){notes.Add($"{entry.Key}: IL incompatível; ignorado");continue;}
      for(int i=0;i<original.Count;i++){
        if(!IsLiteral(original[i])||!Equals(Value(original[i]),Value(newIL[i])))continue;
        var from=Value(original[i]);var to=Value(changedIL[i]);
        if(Equals(from,to))continue;
        if(!Equals(Value(newIL[i]),from)){notes.Add($"{entry.Key}: conflito no literal {i}; ignorado");continue;}
        if(to?.GetType()!=from?.GetType()){notes.Add($"{entry.Key}: mudança de tipo no literal {i}; ignorada");continue;}
        SetValue(newIL[i],to); applied++;
      }
    }
    if(applied>0) c.Write(output);
    return new {kind="managed_literal_migration", applied, output=applied>0?output:null, warnings=notes.Take(60).ToArray(), verified=applied>0?"reopened_check_required":"not_applicable"};
  }
  static object ReplaceString(string input,string output,string previous,string replacement){
    if(string.IsNullOrEmpty(previous)||previous.Length>500||replacement.Length>500)throw new ArgumentException("Texto inválido");
    using var assembly=Read(input);
    var occurrences=Methods(assembly).Values.SelectMany(m=>m.Body.Instructions
       .Where(i=>i.OpCode.Code==Code.Ldstr && (string)i.Operand==previous)
       .Select(i=>new {method=Id(m),instruction=i})).ToList();
    if(occurrences.Count!=1)throw new ArgumentException($"Encontradas {occurrences.Count} ocorrências (exige uma correspondência única)");
    occurrences[0].instruction.Operand=replacement;
    assembly.Write(output);
    using var verify=Read(output);
    return new {kind="managed_string_replace",applied=1,method=occurrences[0].method,output,verified="assembly_reopened"};
  }
  public static int Main(string[] args){
    try{
      if(args.Length<2)throw new ArgumentException("Uso: inspect caminho | migrate antigo_original antigo_modificado novo_original saida");
      object report;
      if(args[0]=="inspect") {using var a=Read(args[1]);report=Inspect(a);}
      else if(args[0]=="migrate"&&args.Length==5){report=Transfer(args[1],args[2],args[3],args[4]);}
      else if(args[0]=="replace-string"&&args.Length==5){report=ReplaceString(args[1],args[2],args[3],args[4]);}
      else throw new ArgumentException("Comando inválido");
      Console.WriteLine(JsonSerializer.Serialize(report));return 0;
    }catch(Exception e){Console.Error.WriteLine("Assembly não processado: "+e.GetType().Name+": "+e.Message);return 2;}
  }
}
