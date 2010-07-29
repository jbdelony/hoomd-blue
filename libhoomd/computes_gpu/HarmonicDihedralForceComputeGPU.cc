/*
Highly Optimized Object-oriented Many-particle Dynamics -- Blue Edition
(HOOMD-blue) Open Source Software License Copyright 2008, 2009 Ames Laboratory
Iowa State University and The Regents of the University of Michigan All rights
reserved.

HOOMD-blue may contain modifications ("Contributions") provided, and to which
copyright is held, by various Contributors who have granted The Regents of the
University of Michigan the right to modify and/or distribute such Contributions.

Redistribution and use of HOOMD-blue, in source and binary forms, with or
without modification, are permitted, provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright notice, this
list of conditions, and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
list of conditions, and the following disclaimer in the documentation and/or
other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of HOOMD-blue's
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

Disclaimer

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER AND CONTRIBUTORS ``AS IS''
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND/OR
ANY WARRANTIES THAT THIS SOFTWARE IS FREE OF INFRINGEMENT ARE DISCLAIMED.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

// $Id$
// $URL$
// Maintainer: akohlmey

#ifdef WIN32
#pragma warning( push )
#pragma warning( disable : 4244 )
#endif

#include "HarmonicDihedralForceComputeGPU.h"

#include <boost/python.hpp>
using namespace boost::python;

#include <boost/bind.hpp>
using namespace boost;

using namespace std;

#ifdef ENABLE_CUDA
#include "gpu_settings.h"
#endif

/*! \param sysdef System to compute bond forces on
*/
HarmonicDihedralForceComputeGPU::HarmonicDihedralForceComputeGPU(boost::shared_ptr<SystemDefinition> sysdef)
    : HarmonicDihedralForceCompute(sysdef), m_block_size(64)
    {
    // can't run on the GPU if there aren't any GPUs in the execution configuration
    if (!exec_conf->isCUDAEnabled())
        {
        cerr << endl << "***Error! Creating a DihedralForceComputeGPU with no GPU in the execution configuration" << endl << endl;
        throw std::runtime_error("Error initializing DihedralForceComputeGPU");
        }
        
    // allocate and zero device memory
    cudaMalloc(&m_gpu_params, m_dihedral_data->getNDihedralTypes()*sizeof(float4));
    cudaMemset(m_gpu_params, 0, m_dihedral_data->getNDihedralTypes()*sizeof(float4));
    CHECK_CUDA_ERROR();
        
    m_host_params = new float4[m_dihedral_data->getNDihedralTypes()];
    memset(m_host_params, 0, m_dihedral_data->getNDihedralTypes()*sizeof(float4));
    }

HarmonicDihedralForceComputeGPU::~HarmonicDihedralForceComputeGPU()
    {
    // free memory on the GPU
    cudaFree(m_gpu_params);
    m_gpu_params = NULL;
    CHECK_CUDA_ERROR();
        
    // free memory on the CPU
    delete[] m_host_params;
    m_host_params = NULL;
    }

/*! \param type Type of the dihedral to set parameters for
    \param K Stiffness parameter for the force computation
    \param sign the sign of the cosine term
        \param multiplicity the multiplicity of the cosine term

    Sets parameters for the potential of a particular dihedral type and updates the
    parameters on the GPU.
*/
void HarmonicDihedralForceComputeGPU::setParams(unsigned int type, Scalar K, int sign, unsigned int multiplicity)
    {
    HarmonicDihedralForceCompute::setParams(type, K, sign, multiplicity);
    
    // update the local copy of the memory
    m_host_params[type] = make_float4(float(K), float(sign), float(multiplicity), 0.0f);
    
    // copy the parameters to the GPU
    cudaMemcpy(m_gpu_params, m_host_params, m_dihedral_data->getNDihedralTypes()*sizeof(float4), cudaMemcpyHostToDevice);
    CHECK_CUDA_ERROR();
    }

/*! Internal method for computing the forces on the GPU.
    \post The force data on the GPU is written with the calculated forces

    \param timestep Current time step of the simulation

    Calls gpu_compute_harmonic_dihedral_forces to do the dirty work.
*/
void HarmonicDihedralForceComputeGPU::computeForces(unsigned int timestep)
    {
    // start the profile
    if (m_prof) m_prof->push(exec_conf, "Harmonic Dihedral");
    
    gpu_dihedraltable_array& gpu_dihedraltable = m_dihedral_data->acquireGPU();
    
    // the dihedral table is up to date: we are good to go. Call the kernel
    gpu_pdata_arrays& pdata = m_pdata->acquireReadOnlyGPU();
    gpu_boxsize box = m_pdata->getBoxGPU();
    
    // run the kernel in parallel on all GPUs
    gpu_compute_harmonic_dihedral_forces(m_gpu_forces.d_data,
                                         pdata,
                                         box,
                                         gpu_dihedraltable,
                                         m_gpu_params,
                                         m_dihedral_data->getNDihedralTypes(),
                                         m_block_size);
    CHECK_CUDA_ERROR();
    
    // the force data is now only up to date on the gpu
    m_data_location = gpu;
    
    m_pdata->release();
    
    if (m_prof) m_prof->pop(exec_conf);
    }

void export_HarmonicDihedralForceComputeGPU()
    {
    class_<HarmonicDihedralForceComputeGPU, boost::shared_ptr<HarmonicDihedralForceComputeGPU>, bases<HarmonicDihedralForceCompute>, boost::noncopyable >
    ("HarmonicDihedralForceComputeGPU", init< boost::shared_ptr<SystemDefinition> >())
    .def("setBlockSize", &HarmonicDihedralForceComputeGPU::setBlockSize)
    ;
    }

