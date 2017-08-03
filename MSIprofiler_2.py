 #Isidro Cortes-Ciriano
# Harvard Medical School
# isidrolauscher@gmail.com

# to make numpy divisions show decimal values by default:
# https://stackoverflow.com/questions/1799527/numpy-show-decimal-values-in-array-results
from __future__ import division

from bisect import bisect

match_score = 1 # score for a match
mismatch_score = -6 # score penalty for a mismatch
fail_score = -1 # score value to stop searching
min_score = 4 # minimum score value to pass. The minimum length of MS repeats detected is mon_score + 4
#--------------------------------------------------------------------------------------------------------------------------------------
import pysam
import os
import multiprocessing as mp
import argparse
import csv
import numpy as np
import utils
from scipy import stats
#from sputnik import find_repeatsfrom sputnik_target import find_repeats_target

#from parameters import *
import pickle
#--------------------------------------------------------------------------------------------------------------------------------------

def find_repeats(seq,flank_size):
    bases=len(seq)
    flank_size = flank_size-1
    # save output as a list of lists
    out = []; exclude=set() # use sets: they are much faster to apply 'in'
    for ru in rus:
        positions_motif = range(0,ru)
        nb_positions_motif = len(positions_motif)
        not_found = True
        base = flank_size
        while base < bases-flank_size: #and base not in exclude:
            if base in exclude:
                base+=1
                continue
            elif not_found:
                test_pos=base+ru
                current_pos=base
            else:
                current_pos=base
                not_found=True
                test_pos=test_pos+ru
            pos_in_motif = 0
            score = 0; depth = 0; keep = 0
            max_observed_score = 0
            scores = []
            while ( (test_pos ) < (bases-flank_size) )  and  score > fail_score and test_pos not in exclude:
                match = (seq[current_pos + pos_in_motif] == seq[test_pos])
                if match:
                    test_pos+=1
                    pos_in_motif = positions_motif[(pos_in_motif + 1) % nb_positions_motif]
                    score+=match_score
                    scores.append(score)
                    depth = 0
                else:
                    score+=mismatch_score
                    scores.append(score)
                    pos_in_motif = positions_motif[(pos_in_motif + 1) % nb_positions_motif]
                    if score > fail_score and depth < 5:
                        depth+=1
                        test_pos +=1
                # keep track of the best observed score
                if score > max_observed_score:
                    max_observed_score = score
                #debugging
            #print "RU current_pos  pos_in_motif  test_pos   bases, score"
                #print ru, current_pos, pos_in_motif, test_pos, bases,score,"\n" #, current_pos + pos_in_motif, bases
            if max_observed_score >= min_score:# and test_pos <= bases-flank_size:
                mm = scores.index(max(scores))
                mm = mm +ru
                if base+mm < (bases-flank_size): # repeat not overlapping flanking region
                   out.append( [ru, base, base+mm, seq[base:base+mm+1]])
                   not_found = False
                exclude.update(range(base,base+mm+1))
                test_pos = base + mm
                base = test_pos
            else:
                pass
            base+=1
        else:
            base+=1
    return out

#--------------------------------------------------------------------------------------------------------------------------------------
# https://stackoverflow.com/questions/212358/binary-search-bisection-in-python
def binary_search(a, x, lo=0, hi=None):  # can't use a to specify default for hi
    hi = hi if hi is not None else len(a)  # hi defaults to len(a)
    pos = bisect.bisect_left(a, x, lo, hi)  # find insertion position
    return (pos if pos != hi and a[pos] == x else -1)
#--------------------------------------------------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='MSIprofiler serves to detect microsatellite instability from sequencing data. Type MSIprofiler.py --help for further instructions.')
parser.add_argument('--tumor_bam', help='Tumor bam file name',required=True)
parser.add_argument('--normal_bam', help='Normal bam file name',required=True)
parser.add_argument('--bed', help='Input bedfile name',required=True)
parser.add_argument('--chromosomes', help='Chromosomes to be phased',required=True, nargs='+')#
parser.add_argument('--fasta', help='Path to the directory containing the fasta sequences (one per chromosome). The expected names for the fasta files are e.g. chr1.fa',required=True)
parser.add_argument('--reference_set', help='Path to the directory containing the reference sets of microsatellites',required=True)
parser.add_argument('--output_prefix', help='Path and prefix for the output files. E.g. path_to_out_dir/out_prefix',required=True)
parser.add_argument('--mode', help='Phased or unphased',required=True,choices=["phased","unphased"])
parser.add_argument('--nprocs', help='Number of processes',required=True,type=int)
parser.add_argument('--rus', help='MS repeat units. Supported from 1 (i.e. mono repeats) to 6 (i.e. hexarepeats)', required=True,nargs='+',type=int)
# Optional arguments
parser.add_argument('--min_MS_length', help='Minimum length of microsatellites to be considered. Minimum available is 6; default is 10.',required=False,default=10,type=int)
parser.add_argument('--max_MS_length', help='Maximum length of microsatellites to be considered. Maximum available is 60; default is 60.',required=False,default=60,type=int)
parser.add_argument('--mapping_quality', help='Minimum mapping quality. Default is 40.',required=False,default=40,type=int)
parser.add_argument('--flank_size', help='Minimum length of the flanking regions. Default is 10',required=False,default=10,type=int)
parser.add_argument('--min_coverage', help='Minimum coverage at each MS locus -both in the case and control bams-. Default is 10',required=False,default=10,type=int)
parser.add_argument('--tolerated_mismatches', help='Maximum number of tolerated mismatches in the flanking regions. Default is 0',required=False,default=0,type=int)

args = parser.parse_args()
args.rus = set(args.rus)
rus=args.rus

for ru in args.rus:
    if ru not in [1,2,3,4,5,6]:
        print ru, type(ru)
        raise "Valid repeat units (rus) are 1, 2, 3, 4, 5, 6 or any combination thereof"

chrs=["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","X","Y"]
for cc in args.chromosomes:
    if cc not in chrs:
        raise "Valid chromosomes are 1:22, X and Y only"

if os.path.exists(args.tumor_bam) == False:
    raise "Tumor/case bam file does not exist. Exiting.."

if os.path.exists(args.normal_bam) == False:
    raise "Normal bam file does not exist. Exiting."

if os.path.exists(args.reference_set) == False and args.mode in ['unphased']:
    raise "Reference set file does not exist. Exiting.."

if os.path.exists(args.bed) == False and args.mode in ['phased']:
    raise "Bed file containing heterozygous SNPs does not exist. Exiting.."

if os.path.exists(args.fasta) == False:
    raise "Directory containing the fasta files does not exist"

#--------------------------------------------------------------------------------------------------------------------------------------

# sort the input chromosomes to make sure the order is the usual one
args.chromosomes = np.sort(args.chromosomes)

fastas = {}
for ch in args.chromosomes:
    fastas[ch] = pysam.FastaFile(args.fasta+"/chr"+str(ch)+".fa")

# load the heterozygous SNPs detected in bulk
if args.mode in ['phased']:
    with open(args.bed) as bed:
        reader = csv.reader(bed, delimiter="\t")
        sites = list(reader)
#----------------------------------------------------------------------------------------------------------------------------------------------------
# load reference set
#----------------------------------------------------------------------------------------------------------------------------------------------------
def loadcsv(filename, criterion1,criterion2):
    with open(filename, "rb") as csvfile:
        datareader = csv.reader(csvfile, delimiter="\t")
        for row in datareader:
            if int(row[5]) >=criterion1 and int(row[5]) <= criterion2 and int(row[4]) in args.rus:
                yield row
refs = {}
refset_ini_end_dict={}
for ch in args.chromosomes:
    refsetgen = loadcsv(args.reference_set,args.min_MS_length, args.max_MS_length)
    refset = [x for x in refsetgen]
    refs[ch] = refset
    # get the index positions
    refset_ini_end = [x[1] for x in refset]
    refset_ini_end_dict[ch] = refset_ini_end

#------------------------------------------------------------------------------------------------------------
# Function to extract the MS lengths from the reads
#------------------------------------------------------------------------------------------------------------
def unphased(sites,bam_path):
    bamfile = pysam.AlignmentFile(bam_path, "rb")
    dict_out = {}; visited_reads = []
    for site in sites:
        start = int(site[1]); end = int(site[2])+1; chr=site[0]; ru=int(site[4])
        reads = [read for read in bamfile.fetch(str(chr), start,start+1,multiple_iterators=True)]
        reads = [read for read in reads if read.is_proper_pair and read.is_duplicate == False and read.mapping_quality >= args.mapping_quality]
        if  len(reads) > args.min_coverage:
            for read in reads:
                start_read = read.reference_start; end_read = read.reference_end
                read_sequence = read.seq
                reps = utils.find_repeats_target(read_sequence,
                                               args.flank_size,ru)
                if len(reps) > 0:
                    aligned_pos = read.get_reference_positions(full_length=True)
                    try:
                        idx = aligned_pos.index(start)
                    except:
                        continue
                    for microsatellite in reps:
                        ru = microsatellite[0]; rs = microsatellite[1]; re = microsatellite[2]
                        if start != start_read + rs + 1:# do not consider if there are ins/del upstream of the repeat
                            continue
                        difference = re - rs + 1
                        # get flinking sequence from reference
                        flank_left_ref = fastas[chr].fetch("chr"+chr,start_read+rs-args.flank_size, start_read+rs).upper()
                        flank_right_ref = fastas[chr].fetch("chr"+chr,int(site[2])-1,int(site[2])-1 +args.flank_size).upper()
                        # get flinking sequence from the reads
                        posfl = (start_read+rs-args.flank_size)
                        if posfl >= start_read:
                            flank_left = read_sequence[rs-args.flank_size:rs];  mismatches_left = sum(a!=b for a, b in zip(flank_left,flank_left_ref))
                        else:
                            flank_left = ""; mismatches_left=10000
                        posflr = start_read+re+args.flank_size
                        if posflr <= end_read:
                            flank_right = read_sequence[re:re+args.flank_size]; mismatches_right = sum(a!=b for a, b in zip(flank_right,flank_right_ref))
                        else:
                            flank_right = ""; mismatches_right=10000
                        mismatches = mismatches_left + mismatches_right
                        if mismatches <= args.tolerated_mismatches:
                            key_now = site[0] + "\t"+site[1]+"\t"+site[2]+"\t"+site[3]+"\t"+site[4]+"\t"+site[5]+"\t"+site[6]
                            if dict_out.has_key(key_now):
                                dict_out[key_now] = np.append(dict_out[key_now], difference)
                            else:
                                dict_out[key_now] = difference
    bamfile.close()
    return dict_out

#------------------------------------------------------------------------------------------------------------
def phased(sites,bam_path,index):
    bamfile = pysam.AlignmentFile(bam_path, "rb")
    dict_out = {}; visited_reads = []
    for site in sites:
        start = int(site[1]);  end = int(site[2]);  chr=str(site[0]); base1 = site[3]; base2=site[4]; bases = [site[3], site[4] ]
        reads = [read for read in bamfile.fetch(chr, start,end ,multiple_iterators=True)] ## keep this as is, do not put conditions inside here
        reads = [read for read in reads if read.is_proper_pair and read.is_duplicate == False and read.mapping_quality >= args.mapping_quality]
        if  len(reads) > args.min_coverage:
            for read in reads:
                read_sequence = read.seq
                #read_sequence = read.query_alignment_sequence
                reps = find_repeats(read_sequence,args.flank_size)
                if len(reps) > 0:
                    # get the SNP allele in this read
                    start_read = read.reference_start; end_read = read.reference_end
                    aligned_pos = read.get_reference_positions(full_length=True) #True) reports none for soft-clipped positions
                    try:
                        idx = aligned_pos.index(start)
                    except:
                        continue
                    snp_read = read_sequence[idx]
                    if snp_read not in bases:
                        continue
                    for microsatellite in reps:
                        ru = microsatellite[0]; rs = microsatellite[1]; re = microsatellite[2]; difference = re - rs +1
                        # use the reference set here to get the position on the right
                        ini = start_read + rs  #
                        idx2=binary_search(refset_ini_end_dict[chr],str(ini+1))
                        #print "read, start_read, aligned_pos, idx, snp_read, microsatellite"
                        #print read_sequence,start_read, aligned_pos, idx, snp_read, microsatellite,read_sequence[idx-3:idx+3],"\n\n\n"
                        if idx2 == -1:
                            continue
                        refset_now = refs[chr][idx2]
                        diff_ref = int(refset_now[2])- int(refset_now[1])  + 1
                        flank_right_ref = fastas[chr].fetch("chr"+str(site[0]), ini +diff_ref, ini +diff_ref+args.flank_size).upper()
                        flank_left_ref = fastas[chr].fetch("chr"+str(site[0]),ini-args.flank_size, ini).upper()
                        posfl = (start_read+rs-args.flank_size)
                        if posfl >= start_read:
                            flank_left = read_sequence[rs-args.flank_size:rs]; mismatches_left = sum(a!=b for a, b in zip(flank_left,flank_left_ref))
                        else:
                            flank_left = ""; mismatches_left = 10000
                        posflr = start_read+re+args.flank_size
                        if posflr <= end_read:
                            flank_right = read_sequence[re+1:re+1+args.flank_size]; mismatches_right = sum(a!=b for a, b in zip(flank_right,flank_right_ref))
                        else:
                            flank_right = ""; mismatches_right = 10000
                        mismatches = mismatches_left + mismatches_right
                        #print microsatellite,difference, site,snp_read,read_sequence[idx-2:idx+2],read_sequence[idx-10:idx+10], diff_ref,flank_right, flank_right_ref, "     ", flank_left, flank_left_ref,"  ",ini,start_read+rs,"\n\n"
                        #print read,"\n\n"
                            #print microsatellite,flank_right, flank_right_ref,flank_right_ref, "     ", flank_left, flank_left_ref,flank_left_ref,"  ",ini,start_read+rs,"\n\n"
                        if mismatches <= args.tolerated_mismatches:
                            key_now = site[0] + "\t"+str(ini)+"\t"+ refset_now[3] + "\t"+ refset_now[4] + "\t"+ refset_now[5] + "\t"+ refset_now[6]+"\t"+snp_read+"\t"+str(site[1])
                            if dict_out.has_key(key_now):
                                dict_out[key_now] = np.append(dict_out[key_now], difference)
                            else:
                                dict_out[key_now] = difference
    bamfile.close()
    return dict_out

#--------------------------------------------------------------------------------------------------------------------------------------------------
# PHASED
#--------------------------------------------------------------------------------------------------------------------------------------------------
if args.mode in ['phased']:
    # this list will contain the dictionaries returned by the different processes
    read_lengths_tumor = []
    read_lengths_normal = []
    #------------------------------------------------------
    print "PHASED: Extracting MS repeats from tumor bam file..\n"
    #------------------------------------------------------

    def log_result(result):
        read_lengths_tumor.append(result)

    if args.nprocs == None or args.nprocs == 0:
        args.nprocs = mp.cpu_count()
    if args.nprocs == 1:
        read_lengths_tumor = phased(sites,args.tumor_bam,1)
    else:
        pool = mp.Pool(args.nprocs)
        chunk_size= int(len(sites)/args.nprocs)
        for index in np.arange(0,args.nprocs):
            if index != (args.nprocs-1):
                pool.apply_async(phased, args = (sites[index*chunk_size:(index+1)*chunk_size], args.tumor_bam,index,), callback = log_result)
            else:
                pool.apply_async(phased, args = (sites[index*chunk_size: len(sites)], args.tumor_bam,index,), callback = log_result)
        # close the pool
        pool.close()
        pool.join()


    #------------------------------------------------------
    print "PHASED: tumor/case bam file processed correctly..\n"
    #------------------------------------------------------
    #------------------------------------------------------------------------------------------------------------
    #------------------------------------------------------
    print "PHASED: extracting MS repeats from normal bam file..\n"
    #------------------------------------------------------
    def log_result(result):
        read_lengths_normal.append(result)

    if args.nprocs == None:
        args.nprocs = mp.cpu_count()

    if args.nprocs == 1:
        read_lengths_normal = phased(sites,args.normal_bam,1)
    else:
        pool = mp.Pool(args.nprocs)
        chunk_size= int(len(sites)/args.nprocs)
        for index in np.arange(0,args.nprocs):
            if index != (args.nprocs-1):
                pool.apply_async(phased, args = (sites[index*chunk_size:(index+1)*chunk_size], args.normal_bam,index,), callback = log_result)
            else:
                pool.apply_async(phased, args = (sites[index*chunk_size:len(sites)], args.normal_bam,index,), callback = log_result)
        pool.close()
        pool.join()

    #------------------------------------------------------
    print "Normal bam file processed correctly..\n"
    #------------------------------------------------------

    all_normal={}; all_tumor={}
    if args.nprocs >1:
        for i in range(1,args.nprocs):
            all_normal.update(read_lengths_normal[i])
            all_tumor.update(read_lengths_tumor[i])
    else:
        all_normal = read_lengths_normal
        all_tumor = read_lengths_tumor

    keys_normal =  set(all_normal);  keys_tumor =  set(all_tumor)
    common_keys= keys_tumor.intersection(keys_normal); counter = 0

    #----------------------------------------------------------------------------------------------------------------------
    # genotype the phased calls
    #----------------------------------------------------------------------------------------------------------------------
    f = open(args.output_prefix+'_phased.txt', 'w')
    for name in common_keys:
        nor = all_normal[name]
        canc = all_tumor[name]
        if isinstance(nor,int) == False and isinstance(canc,int) == False:
            if len(nor) >= args.min_coverage and len(canc) >= args.min_coverage:
                pval_ks = stats.ks_2samp(nor, canc)[1]
                f.write(name+"\t"+ ",".join([str(x) for x in nor])  +"\t"+ ",".join([str(x) for x in canc ]) +"\t"+str(pval_ks)+"\n")
    f.close()

    print "Phased microsatellites writen to: "+args.output_prefix+'_phased.txt'

    #------------------------------------------------------
    print "Calculation of the phased microsatellites finished successfully.."
    #------------------------------------------------------

#-------------------------------------------------------------------------------------------------------------------------------------------
# UNPHASED
#-------------------------------------------------------------------------------------------------------------------------------------------
if args.mode in ['unphased']:
    #------------------------------------------------------
    print "Extracting MS repeats (UNPHASED) from tumor bam file..\n"
    #------------------------------------------------------
    read_lengths_tumor_unphased = []
    def log_result(result):
        read_lengths_tumor_unphased.append(result)
    pool = mp.Pool(args.nprocs)
    chunk_size= int( len(refset)/args.nprocs )

    if args.nprocs == 0:
        print "The value of the argument nprocs needs to be at least 1\n\n"
        raise
    if args.nprocs == None:
        args.nprocs = mp.cpu_count()
    if args.nprocs == 1:
        read_lengths_tumor_unphased = unphased(refset,args.tumor_bam)
    else:
        for index in np.arange(0,args.nprocs):
            if index != (args.nprocs-1):
                pool.apply_async(unphased, args = (refset[index*chunk_size:(index+1)*chunk_size], args.tumor_bam,), callback = log_result)
            else:
                pool.apply_async(unphased, args = (refset[index*chunk_size:len(refset)], args.tumor_bam,), callback = log_result)
        pool.close()
        pool.join()

    #------------------------------------------------------
    print "UNPHASED: tumor bam file processed correctly..\n"
    #------------------------------------------------------
    #------------------------------------------------------
    print "Extracting MS repeats (UNPHASED) from normal bam file..\n"
    #------------------------------------------------------
    read_lengths_normal_unphased = []
    def log_result(result):
        read_lengths_normal_unphased.append(result)
    pool = mp.Pool(args.nprocs)

    if args.nprocs == 1:
        read_lengths_normal_unphased = unphased(refset,args.normal_bam)
    else:
        for index in np.arange(0,args.nprocs):
            if index != (args.nprocs-1):
                pool.apply_async(unphased, args = (refset[index*chunk_size:(index+1)*chunk_size], args.normal_bam,), callback = log_result)
            else:
                pool.apply_async(unphased, args = (refset[index*chunk_size:len(refset)], args.normal_bam,), callback = log_result)
        pool.close()
        pool.join()

    #------------------------------------------------------
    print "UNPHASED: normal bam file processed correctly..\n"
    #------------------------------------------------------
    f = open(args.output_prefix+'_unphased.txt', 'w')
    all_normal={};all_tumor={}
    if args.nprocs >1:
        for i in range(1,args.nprocs):
            all_normal.update(read_lengths_normal_unphased[i])
            all_tumor.update(read_lengths_tumor_unphased[i])
    else:
        all_normal = read_lengths_normal_unphased
        all_tumor = read_lengths_tumor_unphased

    keys_normal = set(all_normal)
    keys_tumor = set(all_tumor)
    common_keys= keys_tumor.intersection(keys_normal)
    counter = 0

    for name in common_keys:
        nor = all_normal[name]
        canc = all_tumor[name]
        if isinstance(nor,int) == False and isinstance(canc,int) == False:
            if len(nor) >= args.min_coverage and len(canc) >= args.min_coverage:
                pval = stats.ks_2samp(nor,canc)[1] #read_lengths_normal_unphased[i][name], read_lengths_tumor_unphased[i][name])[1]
                mo = stats.mode(nor)
                percentage = (nor == mo).sum() / len(nor)
                confidence = "high" if percentage >=.7 else "low"
                f.write(name+"\t"+ ",".join([str(x) for x in nor])  +"\t"+ ",".join([str(x) for x in canc ]) +"\t"+str(pval)+"\t"+confidence+"\n")
    f.close()
#------------------------------------------------------
print "All calculations finished successfully!\n"
#------------------------------------------------------
