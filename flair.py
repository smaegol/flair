""" AD Tang 2018 """

import sys, argparse, subprocess, os
from subprocess import Popen, PIPE

if len(sys.argv) > 1 and sys.argv[1] == 'align':
	mode = 'align'
elif len(sys.argv) > 1 and sys.argv[1] == 'correct':
	mode = 'correct'
elif len(sys.argv) > 1 and sys.argv[1] == 'collapse':
	mode = 'collapse'
else:
	sys.stderr.write('usage: python flair.py <mode> --help \n')
	sys.stderr.write('modes: align, correct, collapse\n')
	sys.exit()

path = sys.argv[0][:sys.argv[0].rfind('/')+1] if '/' in sys.argv[0] else ''
if mode == 'align':
	parser = argparse.ArgumentParser(description='flair-align parse options', \
				usage='python flair.py align -r <reads.fq>/<reads.fa> -g genome.fa [options]')
	parser.add_argument('align')
	required = parser.add_argument_group('required named arguments')
	required.add_argument('-r', '--reads', action='store', dest='r', \
		type=str, required=True, help='FastA/FastQ files of raw reads')
	required.add_argument('-g', '--genome', action='store', dest='g', \
		type=str, required=True, help='FastA of reference genome')
	parser.add_argument('-m', '--minimap2', type=str, default='minimap2', \
		action='store', dest='m', help='path to minimap2 if not in $PATH')
	parser.add_argument('-o', '--output', \
		action='store', dest='o', default='flair.aligned', help='output file name base')
	parser.add_argument('-t', '--threads', type=str, \
		action='store', dest='t', default='4', help='minimap2 number of threads (4)')
	parser.add_argument('-sam', '--samtools', \
		action='store', dest='sam', default='samtools', help='samtools executable path if not in $PATH')
	parser.add_argument('-c', '--chromsizes', type=str, \
		action='store', dest='c', default='', help='chromosome sizes tab-separated file, used for converting sam to \
		genome-browser compatible psl file')
	parser.add_argument('-n', '--nvrna', action='store_true', dest='n', default=False, help='specify this flag to use \
		native-RNA specific alignment parameters for minimap2')
	parser.add_argument('-p', '--psl', action='store_true', dest='p', help='also output sam-converted psl')
	parser.add_argument('-v1.9', '--version1.9', action='store_true', dest='v', help='specify if samtools version 1.9')
	args = parser.parse_args()

	if args.m[-8:] != 'minimap2':
		if args.m[-1] == '/':
			args.m += 'minimap2'
		else:
			args.m += '/minimap2'

	try:
		if args.n:
			subprocess.call([args.m, '-ax', 'splice', '-uf', '-k14', '-t', args.t, '--secondary=no', args.g, args.r], stdout=open(args.o+'.sam', 'w'))			
		else:
			subprocess.call([args.m, '-ax', 'splice', '-t', args.t, '--secondary=no', args.g, args.r], stdout=open(args.o+'.sam', 'w'))
	except:
		sys.stderr.write('Possible minimap2 error, specify executable path with -m\n')
		sys.exit()

	if args.p and args.c:  # sam to psl if desired
		subprocess.call(['python', path+'bin/sam_to_psl.py', args.o+'.sam', args.o+'.psl', args.c])
	elif args.p:
		subprocess.call(['python', path+'bin/sam_to_psl.py', args.o+'.sam', args.o+'.psl'])
	
	sys.stderr.write('Converting sam output to bed\n')
	if subprocess.call([args.sam, 'view', '-h', '-Sb', '-@', args.t, args.o+'.sam'], stdout=open(args.o+'.unsorted.bam', 'w')):
		# calls samtools view, if an error code that != 0 results, then exit out of flair.py
		sys.stderr.write('Possible issue with samtools executable\n')
		sys.exit()

	if args.v:  # samtools verison 1.9
		subprocess.call([args.sam, 'sort', '-@', args.t, args.o+'.unsorted.bam', '-o', args.o+'.bam'])
	elif subprocess.call([args.sam, 'sort', '-@', args.t, args.o+'unsorted.bam', args.o]):
		sys.stderr.write('If using samtools v1.9, please specify -v1.9 argument\n')
		sys.exit()

	subprocess.call([args.sam, 'index', args.o+'.bam'])
	subprocess.call(['python', path+'bin/bam2Bed12.py', '-i', args.o+'.bam'], stdout=open(args.o+'.bed', 'w'))

elif mode == 'correct':
	parser = argparse.ArgumentParser(description='flair-correct parse options', \
				usage='python flair.py correct -f annotation.gtf -c chromsizes.tsv -q query.bed12 [options]')
	parser.add_argument('correct')
	required = parser.add_argument_group('required named arguments')
	required.add_argument('-f', '--gtf', default='', \
		action='store', dest='f', help='GTF annotation file, used for associating gene names to reads')
	required.add_argument('-q', '--query', type=str, default='', required=True, \
		action='store', dest='q', help='uncorrected bed12 file')
	required.add_argument('-c', '--chromsizes', type=str, \
		action='store', dest='c', default='', help='chromosome sizes tab-separated file')
	parser.add_argument('-j', '--shortread', action='store', dest='j', type=str, default='', \
		help='bed format splice junctions from short-read sequencing')
	parser.add_argument('-n', '--nvrna', action='store_true', dest='n', default=False, help='specify this flag to keep\
		the strand of a read consistent after correction')
	parser.add_argument('-t', '--threads', type=str, \
		action='store', dest='t', default='4', help='splice site correction script number of threads (4)')
	parser.add_argument('-w', '--window', action='store', dest='w', default='10', \
		help='window size for correcting splice sites (W=10)')
	parser.add_argument('-o', '--output', \
		action='store', dest='o', default='flair', help='output name base')
	args = parser.parse_args()

	correction_cmd = ['python', path+'bin/ssCorrect.py', '-i', args.q, '-g', args.f, \
			'-w', args.w, '-p', args.t, '-o', args.o, '--quiet', '--progress']
	if not args.n:
		correction_cmd += ['--correctStrand']
	if args.j:
		correction_cmd += ['-j', args.j]
	subprocess.call(correction_cmd)

	subprocess.call(['python', path+'bin/bed_to_psl.py', args.c, args.o+'_all_corrected.bed', args.o+'_all_corrected.unnamed.psl'])

	subprocess.call(['python', path+'bin/identify_annotated_gene.py', \
		args.o+'_all_corrected.unnamed.psl', args.f, args.o+'_all_corrected.psl'])
	subprocess.call(['rm', args.o+'_all_corrected.unnamed.psl'])

elif mode == 'collapse':
	parser = argparse.ArgumentParser(description='flair-collapse parse options', \
				usage='python flair.py correct -r <reads.fq>/<reads.fa> -q <query.psl>/<query.bed12> -g genome.fa [options]')
	parser.add_argument('collapse')
	required = parser.add_argument_group('required named arguments')
	required.add_argument('-r', '--reads', action='store', dest='r', \
		type=str, required=True, help='FastA/FastQ files of raw reads')
	required.add_argument('-q', '--query', type=str, default='', required=True, \
		action='store', dest='q', help='PSL file of aligned/corrected reads')
	required.add_argument('-g', '--genome', action='store', dest='g', \
		type=str, required=True, help='FastA of reference genome')
	parser.add_argument('-f', '--gtf', default='', \
		action='store', dest='f', help='GTF annotation file, used for renaming annotated isoforms')
	parser.add_argument('-m', '--minimap2', type=str, default='minimap2', \
		action='store', dest='m', help='path to minimap2 if not in $PATH')
	parser.add_argument('-t', '--threads', type=str, \
		action='store', dest='t', default='4', help='minimap2 number of threads (T=4)')
	parser.add_argument('-p', '--promoters', \
		action='store', dest='p', default='', help='promoter regions bed file to identify full-length reads')
	parser.add_argument('-b', '--bedtools', \
		action='store', dest='b', default='bedtools', help='bedtools executable path, provide if promoter regions specified')
	parser.add_argument('-sam', '--samtools', \
		action='store', dest='sam', default='samtools', help='samtools executable path if not in $PATH')
	parser.add_argument('-w', '--window', default='20', \
		action='store', dest='w', help='window size for comparing TSS/TES (W=20)')
	parser.add_argument('-s', '--support', default='3', \
		action='store', dest='s', help='minimum number of supporting reads for an isoform (S=3)')
	parser.add_argument('-n', '--no_redundant', default='none', \
		action='store', dest='n', help='Report options include: \
		none: best TSSs/TESs chosen for each unique set of splice junctions; \
		longest: one TSS/TES chosen to maximize length; \
		best_only: one best TSS/TES used in conjunction chosen (default: none)')
	parser.add_argument('-e', '--filter', default='default', \
		action='store', dest='e', help='Report options include: \
		default--full-length isoforms only \
		comprehensive--default set + partial isoforms \
		ginormous--comprehensive + single exon subset isoforms')
	parser.add_argument('-o', '--output', default='flair.collapse', \
		action='store', dest='o', help='output file name base for FLAIR isoforms')
	args = parser.parse_args()

	if args.m[-8:] != 'minimap2':
		if args.m[-1] == '/':
			args.m += 'minimap2'
		else:
			args.m += '/minimap2'

	precollapse = args.q  # filename
	if args.p:
		sys.stderr.write('Filtering out reads without promoter-supported TSS\n')
		subprocess.call(['python', path+'bin/pull_starts.py', args.q, args.q[:-3]+'tss.bed'])
		subprocess.call([args.b, 'intersect', '-a', args.q[:-3]+'tss.bed', '-b', args.p], \
			stdout=open(args.q[:-3]+'promoter_intersect.bed', 'w'))
		subprocess.call(['python', path+'bin/psl_reads_from_bed.py', args.q[:-3]+'promoter_intersect.bed', \
			args.q, args.q[:-3]+'promotersupported.psl'])
		precollapse = args.q[:-3]+'promotersupported.psl'

	sys.stderr.write('Collapsing isoforms\n')
	if subprocess.call(['python', path+'bin/collapse_isoforms_precise.py', '-q', precollapse, \
		'-w', args.w, '-s', '1', '-n', args.n, '-o', args.q[:-3]+'firstpass.psl']):
		sys.exit()

	sys.stderr.write('Filtering isoforms\n')  # filter more
	if subprocess.call(['python', path+'bin/filter_collapsed_isoforms.py', args.q[:-3]+'firstpass.psl', \
		args.e, args.q[:-3]+'firstpass.filtered.psl']):
		sys.exit()
	subprocess.call(['mv', args.q[:-3]+'firstpass.filtered.psl', args.q[:-3]+'firstpass.psl'])

	if args.f:
		sys.stderr.write('Renaming isoforms\n')
		if subprocess.call(['python', path+'bin/identify_similar_annotated_isoform.py', \
			args.q[:-3]+'firstpass.psl', args.f, args.q[:-3]+'firstpass.renamed.psl']):
			sys.exit()
		subprocess.call(['mv', args.q[:-3]+'firstpass.renamed.psl', args.q[:-3]+'firstpass.psl'])

	subprocess.call(['python', path+'bin/psl_to_sequence.py', args.q[:-3]+'firstpass.psl', \
		args.g, args.q[:-3]+'firstpass.fa'])
	
	sys.stderr.write('Aligning reads to first-pass isoform reference\n')
	try:
		subprocess.call([args.m, '-a', '-t', args.t, '--secondary=no', \
			args.q[:-3]+'firstpass.fa', args.r], stdout=open(args.q[:-3]+'firstpass.sam', "w"))
		subprocess.call([args.sam, 'view', '-q', '1', '-S', args.q[:-3]+'firstpass.sam'], stdout=open(args.q[:-3]+'firstpass.q1.sam', "w"))
	except:
		sys.stderr.write('Possible minimap2/samtools error, specify paths or make sure they are in $PATH\n')
		sys.exit()
		
	sys.stderr.write('Counting isoform expression\n')
	subprocess.call(['python', path+'bin/count_sam_genes.py', args.q[:-3]+'firstpass.q1.sam', \
		args.q[:-3]+'firstpass.q1.counts'])
	
	sys.stderr.write('Filtering isoforms by read coverage\n')
	subprocess.call(['python', path+'bin/match_counts.py', args.q[:-3]+'firstpass.q1.counts', \
		args.q[:-3]+'firstpass.psl', args.s, args.q[:-3]+'isoforms.psl'])
	subprocess.call(['python', path+'bin/psl_to_sequence.py', args.q[:-3]+'isoforms.psl', \
		args.g, args.q[:-3]+'isoforms.fa'])

	subprocess.call(['mv', args.q[:-3]+'isoforms.psl', args.o+'.isoforms.psl'])
	subprocess.call(['mv', args.q[:-3]+'isoforms.fa', args.o+'.isoforms.fa'])
	
	sys.stderr.write('Removing intermediate files/done\n')
	if args.p:
		subprocess.call(['rm', args.q[:-3]+'promoter_intersect.bed'])
		subprocess.call(['rm', args.q[:-3]+'promotersupported.psl'])
	# subprocess.call(['rm', args.q[:-3]+'firstpass.psl'])
	subprocess.call(['rm', args.q[:-3]+'firstpass.fa'])
	subprocess.call(['rm', args.q[:-3]+'firstpass.sam'])
	subprocess.call(['rm', args.q[:-3]+'firstpass.q1.counts'])

