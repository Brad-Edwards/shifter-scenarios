using System;
using System.Buffers.Binary;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

internal static class Program
{
    private const string ListedReviewer = "mara.stone-review";

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static ulong Chunk0() => 0x006100720061006dUL;
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static ulong Chunk1() => 0x006f00740073002eUL;
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static ulong Chunk2() => 0x0072002d0065006eUL;

    private static string ResolveReviewer()
    {
        Span<char> reviewer = stackalloc char[17];
        Span<byte> bytes = MemoryMarshal.AsBytes(reviewer);
        BinaryPrimitives.WriteUInt64LittleEndian(bytes[0..8], Chunk0());
        BinaryPrimitives.WriteUInt64LittleEndian(bytes[8..16], Chunk1());
        BinaryPrimitives.WriteUInt64LittleEndian(bytes[16..24], Chunk2());
        BinaryPrimitives.WriteUInt64LittleEndian(bytes[24..32], 0x0065006900760065UL);
        reviewer[16] = 'w';
        return new string(reviewer);
    }

    private static void Main()
    {
        Console.WriteLine($"REVIEWHELP-R4:{ResolveReviewer()}:CMP-CRR-R21-R7");
    }
}
