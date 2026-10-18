"""
After running Job 1 on a real Hadoop cluster:
  hdfs dfs -getmerge /safelink/bloom_out bloom_part.txt
  python mapreduce/build_from_hadoop_output.py bloom_part.txt <m> <k>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mapreduce.run_local import build_bloom_from_output  # noqa: E402

path, m, k = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(path) as f:
    build_bloom_from_output(f.read(), m, k)
