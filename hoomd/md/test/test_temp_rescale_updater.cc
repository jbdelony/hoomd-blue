// Copyright (c) 2009-2021 The Regents of the University of Michigan
// This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.


// this include is necessary to get MPI included before anything else to support intel MPI
#include "hoomd/ExecutionConfiguration.h"

#include <iostream>

#include <memory>

#include "hoomd/md/ComputeThermo.h"
#include "hoomd/md/TempRescaleUpdater.h"
#include "hoomd/filter/ParticleFilterAll.h"

#ifdef ENABLE_HIP
#include "hoomd/md/ComputeThermoGPU.h"
#endif

#include <math.h>

using namespace std;

#include "hoomd/test/upp11_config.h"
HOOMD_UP_MAIN();


/*! \file temp_rescale_updater_test.cc
    \brief Unit tests for the ComputeThermo and TempRescaleUpdater classes.
    \ingroup unit_tests
*/

//! test case to verify proper operation of ComputeThermo
UP_TEST( ComputeThermo_basic )
    {
    // verify that we can constructe a TempCompute properly
    // create a simple particle data to test with
    std::shared_ptr<SystemDefinition> sysdef(new SystemDefinition(2, BoxDim(1000.0), 4));
    std::shared_ptr<ParticleData> pdata = sysdef->getParticleData();

    {
    ArrayHandle<Scalar4> h_pos(pdata->getPositions(), access_location::host, access_mode::readwrite);
    ArrayHandle<Scalar4> h_vel(pdata->getVelocities(), access_location::host, access_mode::readwrite);

    h_pos.data[0].x = h_pos.data[0].y = h_pos.data[0].z = 0.0;
    h_vel.data[0].x = 1.0; h_vel.data[0].y = 2.0; h_vel.data[0].z = 3.0;
    h_pos.data[1].x = h_pos.data[1].y = h_pos.data[1].z = 1.0;
    h_vel.data[1].x = 4.0; h_vel.data[1].y = 5.0; h_vel.data[1].z = 6.0;
    }

    // construct a TempCompute and see that everything is set properly
    std::shared_ptr<ParticleFilter> selector_all(new ParticleFilterAll());
    std::shared_ptr<ParticleGroup> group_all(new ParticleGroup(sysdef, selector_all));
    std::shared_ptr<ComputeThermo> tc(new ComputeThermo(sysdef, group_all));

    // check that we can actually compute temperature
    group_all->setTranslationalDOF(3*pdata->getN());
    tc->compute(0);
    MY_CHECK_CLOSE(tc->getTemperature(), 15.1666666666666666666667, tol);
    }

#ifdef ENABLE_HIP
//! test case to verify proper operation of ComputeThermoGPU
UP_TEST( ComputeThermoGPU_basic )
    {
    // verify that we can constructe a TempCompute properly
    // create a simple particle data to test with
    std::shared_ptr<SystemDefinition> sysdef(new SystemDefinition(2, BoxDim(1000.0), 4));
    std::shared_ptr<ParticleData> pdata = sysdef->getParticleData();

    {
    ArrayHandle<Scalar4> h_pos(pdata->getPositions(), access_location::host, access_mode::readwrite);
    ArrayHandle<Scalar4> h_vel(pdata->getVelocities(), access_location::host, access_mode::readwrite);
    h_pos.data[0].x = h_pos.data[0].y = h_pos.data[0].z = 0.0;
    h_vel.data[0].x = 3.0; h_vel.data[0].y = 2.0; h_vel.data[0].z = 3.0;
    h_pos.data[1].x = h_pos.data[1].y = h_pos.data[1].z = 1.0;
    h_vel.data[1].x = 4.0; h_vel.data[1].y = 5.0; h_vel.data[1].z = 6.0;
    }

    // construct a TempCompute and see that everything is set properly
    std::shared_ptr<ParticleFilter> selector_all(new ParticleFilterAll());
    std::shared_ptr<ParticleGroup> group_all(new ParticleGroup(sysdef, selector_all));
    std::shared_ptr<ComputeThermoGPU> tc(new ComputeThermoGPU(sysdef, group_all));

    // check that we can actually compute temperature
    group_all->setTranslationalDOF(3*pdata->getN());
    tc->compute(0);
    Scalar cur_T = tc->getTemperature();
    cout << "Testing: T=" << cur_T << endl;
    MY_CHECK_CLOSE(cur_T, 16.5, tol);
    }
#endif

//! test case to verify proper operation of TempRescaleUpdater
UP_TEST( TempRescaleUpdater_basic )
    {
    // create a simple particle data to test with
    std::shared_ptr<SystemDefinition> sysdef(new SystemDefinition(2, BoxDim(1000.0), 4));
    std::shared_ptr<ParticleData> pdata = sysdef->getParticleData();

    {
    ArrayHandle<Scalar4> h_pos(pdata->getPositions(), access_location::host, access_mode::readwrite);
    ArrayHandle<Scalar4> h_vel(pdata->getVelocities(), access_location::host, access_mode::readwrite);
    h_pos.data[0].x = h_pos.data[0].y = h_pos.data[0].z = 0.0;
    h_vel.data[0].x = 1.0; h_vel.data[0].y = 2.0; h_vel.data[0].z = 3.0;
    h_pos.data[1].x = h_pos.data[1].y = h_pos.data[1].z = 1.0;
    h_vel.data[1].x = 4.0; h_vel.data[1].y = 5.0; h_vel.data[1].z = 6.0;
    }

    // construct a ComputeThermo for the updater
    std::shared_ptr<ParticleFilter> selector_all(new ParticleFilterAll());
    std::shared_ptr<ParticleGroup> group_all(new ParticleGroup(sysdef, selector_all));
    std::shared_ptr<ComputeThermo> tc(new ComputeThermo(sysdef, group_all));
    group_all->setTranslationalDOF(3);


    // variant T for the rescaler
    std::shared_ptr<VariantConstant> T_variant(new VariantConstant(1.2));

    // construct the updater and make sure everything is set properly
    std::shared_ptr<TempRescaleUpdater> rescaler(new TempRescaleUpdater(sysdef, tc, T_variant));

    // run the updater and check the new temperature
    rescaler->update(0);
    tc->compute(1);
    MY_CHECK_CLOSE(tc->getTemperature(), 1.2, tol);

    // check that the setT method works
    std::shared_ptr<VariantConstant> T_variant2(new VariantConstant(2.0));
    rescaler->setT(T_variant2);
    rescaler->update(1);
    tc->compute(2);
    MY_CHECK_CLOSE(tc->getTemperature(), 2.0, tol);
    }
