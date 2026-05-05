###############################################################################
# IA32_GNU:		Intel Core/Xeon with Linux using GNU compiler gfortran.
###############################################################################
F90_SER = gfortran
F90_OMP = gfortran
F90_MPI = mpif90
FLAGS_OPT = -O
# from version 10 and higher, gfortran does not accept argument mismatches; see https://gcc.gnu.org/gcc-10/porting_to.html
FLAGS_MSC = -w -fno-second-underscore -fallow-argument-mismatch
FLAGS90_MSC = $(FLAGS_MSC) -ffree-line-length-none
FLAGS_DYN =
FLAGS_SER =
FLAGS_OMP = -fopenmp
FLAGS_MPI =
METISROOT =
ifneq ($(METISROOT),)
  LIBS_SER = -L$(METISROOT)/lib -lmetis -lGKlib
  LIBS_OMP = -L$(METISROOT)/lib -lmetis -lGKlib -static-libgcc
  LIBS_MPI = -L$(METISROOT)/lib -lmetis -lGKlib
  PART_OBJS = SwanParallel.o
else
  LIBS_SER =
  LIBS_OMP = -static-libgcc
  LIBS_MPI =
  PART_OBJS =
endif
NETCDFROOT =
ifneq ($(NETCDFROOT),)
  INCS_SER = -I$(NETCDFROOT)/include
  INCS_OMP = -I$(NETCDFROOT)/include
  INCS_MPI = -I$(NETCDFROOT)/include
  LIBS_SER = $(LIBS_SER) -L$(NETCDFROOT)/lib -lnetcdf -lnetcdff
  LIBS_OMP = $(LIBS_OMP) -L$(NETCDFROOT)/lib -lnetcdf -lnetcdff
  LIBS_MPI = $(LIBS_MPI) -L$(NETCDFROOT)/lib -lnetcdf -lnetcdff
  NCF_OBJS = nctablemd.o agioncmd.o swn_outnc.o
else
  INCS_SER =
  INCS_OMP =
  INCS_MPI =
  NCF_OBJS =
endif
OUT = -o 
EXTO = o
MAKE = make
RM = rm -f
ifneq ($(METISROOT),)
  swch = -unix -metis
else
  swch = -unix
endif
ifneq ($(NETCDFROOT),)
  swch = $(swch) -netcdf
endif
