import struct
import sys
sys.path.append("superSymbolizer")
from ElfBricks import ElfBricks
from lib.CFIInfo import CFIInfo
from lib.LocalSymbolizer import LocalSymbolizer
from lib.Misc import EParser, FunBriefInfo
import json
import re
from SuperSymbolizer import SuperSymbolizer
import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Serializer')
    parser.add_argument('bin_file', type=str)
    parser.add_argument('b2r2_meta_file', type=str)
    parser.add_argument('stat_file', type=str)
    parser.add_argument('--optimization', type=int, default=0)
    parser.add_argument('--syntax', type=str, default='intel')
    parser.add_argument('--no-endbr', dest='endbr', action='store_false')

    args = parser.parse_args()

    sym = SuperSymbolizer(args.bin_file, args.b2r2_meta_file, args.optimization, args.syntax)
    sym.symbolize(args.endbr)
    sym.report_statistics(args.stat_file)
