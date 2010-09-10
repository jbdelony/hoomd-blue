

/**
powered by:
Moscow group.
*/

#include "EAMForceCompute.h"
#include "NeighborList.h"
#include "EAMTexInterForceGPU.cuh"

#include <boost/shared_ptr.hpp>

/*! \file EAMTexInterForceComputeGPU.h
	\brief Declares the class EAMTexInterForceComputeGPU
*/

#ifndef __EAMTexInterForceComputeGPU_H__
#define __EAMTexInterForceComputeGPU_H__

//! Computes Lennard-Jones forces on each particle using the GPU
/*! Calculates the same forces as EAMForceCompute, but on the GPU by using texture memory(cudaArray) with hardware interpolation.
*/
class EAMTexInterForceComputeGPU : public EAMForceCompute
	{
	public:
		//! Constructs the compute
		EAMTexInterForceComputeGPU(boost::shared_ptr<SystemDefinition> sysdef, char *filename, int type_of_file);

		//! Destructor
		virtual ~EAMTexInterForceComputeGPU();


		//! Sets the block size to run at
		void setBlockSize(int block_size);

	protected:
		EAMTexInterData eam_data;
		EAMtex eam_tex_data;
		Scalar * d_atomDerivativeEmbeddingFunction; //!<array F'(rho) for each particle
		int m_block_size;				//!< The block size to run on the GPU

		//! Actually compute the forces
		virtual void computeForces(unsigned int timestep);
	};

//! Exports the EAMTexInterForceComputeGPU class to python
void export_EAMTexInterForceComputeGPU();

#endif
