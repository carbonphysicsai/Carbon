# A fixed Base-only DEVELOPMENT instrument. No eval, package manager, dynamic
# source loading, caller paths, or authority to qualify a reference.
# Conservative periodic Rusanov flux + centered diffusion + SSPRK3. Values are
# nodal point estimates, matching C-04's sampled-state conservative witness;
# they are not asserted to be exact cell averages or certified error bounds.

const METHOD = "julia_periodic_conservative_flux_ssprk3_refinement_v1"
const LAYOUT = "time,x;C;<f8;point_estimate;periodic"
const MAX_STEPS = 200_000

struct NumericalFailure <: Exception end

function parse_request()
    raw = read(stdin, 32769)
    length(raw) <= 32768 || throw(ArgumentError("input"))
    isascii(String(copy(raw))) || throw(ArgumentError("encoding"))
    lines = split(String(raw), '\n'; keepempty=true)
    length(lines) == 16 && lines[end] == "" || throw(ArgumentError("framing"))
    lines[1] == "CARBON_JULIA_BURGERS_REQUEST_V1" || throw(ArgumentError("schema"))
    lines[2] == METHOD && lines[3] == "1.13.0" || throw(ArgumentError("method"))
    for index in (4, 5, 15)
        occursin(r"^sha256:[0-9a-f]{64}$", lines[index]) || throw(ArgumentError("identity"))
    end
    lines[6] == "dimensionless" && lines[7] == LAYOUT || throw(ArgumentError("units"))
    length_value, viscosity, mean_value = parse.(Float64, lines[8:10])
    all(isfinite, (length_value, viscosity, mean_value)) || throw(ArgumentError("finite"))
    length_value > 0 && viscosity > 0 || throw(ArgumentError("domain"))
    occursin(r"^[1-9][0-9]*$", lines[11]) || throw(ArgumentError("grid"))
    points = parse(Int, lines[11])
    32 <= points <= 1024 && ispow2(points) || throw(ArgumentError("grid"))
    cosine = parse.(Float64, split(lines[12], ','))
    sine = parse.(Float64, split(lines[13], ','))
    times = parse.(Float64, split(lines[14], ','))
    length(cosine) == 12 && length(sine) == 12 || throw(ArgumentError("modes"))
    all(isfinite, cosine) && all(isfinite, sine) || throw(ArgumentError("finite"))
    1 <= length(times) <= 256 && all(isfinite, times) || throw(ArgumentError("times"))
    times[1] >= 0 && all(times[i] < times[i+1] for i in 1:length(times)-1) ||
        throw(ArgumentError("ordering"))
    return (; length_value, viscosity, mean_value, points, cosine, sine, times,
            request_digest=String(lines[15]))
end

function rhs!(result, value, flux, dx, viscosity)
    n = length(value)
    for i in 1:n
        right = i == n ? 1 : i + 1
        a, b = value[i], value[right]
        flux[i] = 0.25 * (a*a + b*b) - 0.5 * max(abs(a), abs(b)) * (b-a)
    end
    for i in 1:n
        right = i == n ? 1 : i + 1
        left = i == 1 ? n : i - 1
        result[i] = -(flux[i] - flux[left]) / dx +
            viscosity * (value[right] - 2.0*value[i] + value[left]) / (dx*dx)
    end
end

function solve_grid(request, n)
    dx = request.length_value / n
    state = [request.mean_value + sum(
        request.cosine[m]*cos(2pi*(i-1)*m/n) +
        request.sine[m]*sin(2pi*(i-1)*m/n) for m in 1:12) for i in 1:n]
    all(isfinite, state) || throw(NumericalFailure())
    initial_mean = sum(state) / n
    drift = 0.0
    derivative, flux, first, second = (zeros(n) for _ in 1:4)
    output = Matrix{Float64}(undef, length(request.times), request.points)
    stride = div(n, request.points)
    current = 0.0
    steps = 0
    for (row, target) in enumerate(request.times)
        while current < target
            steps < MAX_STEPS || throw(NumericalFailure())
            remaining = target - current
            rate = maximum(abs, state) / dx + 2.0*request.viscosity / (dx*dx)
            dt = min(remaining, 0.35 / max(rate, floatmin(Float64)))
            isfinite(dt) && dt > 0.0 && current + dt > current || throw(NumericalFailure())
            rhs!(derivative, state, flux, dx, request.viscosity)
            @. first = state + dt*derivative
            rhs!(derivative, first, flux, dx, request.viscosity)
            @. second = 0.75*state + 0.25*(first + dt*derivative)
            rhs!(derivative, second, flux, dx, request.viscosity)
            @. state = (state + 2.0*(second + dt*derivative)) / 3.0
            all(isfinite, state) || throw(NumericalFailure())
            current = dt == remaining ? target : current + dt
            steps += 1
            drift = max(drift, abs(sum(state)/n - initial_mean))
        end
        for column in 1:request.points
            output[row, column] = state[1 + (column-1)*stride]
        end
    end
    return output, steps, drift
end

function refinement(request)
    coarse_points = max(64, request.points)
    coarse, coarse_steps, coarse_drift = solve_grid(request, coarse_points)
    fine, fine_steps, fine_drift = solve_grid(request, 2*coarse_points)
    difference = fine - coarse
    rms = sqrt(sum(abs2, difference) / length(difference))
    maximum_difference = maximum(abs, difference)
    all(isfinite, (rms, maximum_difference, coarse_drift, fine_drift)) ||
        throw(NumericalFailure())
    return (; fine, coarse_points, coarse_steps, fine_steps, coarse_drift,
            fine_drift, rms, maximum_difference)
end

function main()
    VERSION == v"1.13.0" || return 21
    request = try
        parse_request()
    catch
        return 20
    end
    measured = try
        @timed refinement(request)
    catch error
        return error isa NumericalFailure ? 22 : 23
    end
    result = measured.value
    fields = (
        "CARBON_JULIA_BURGERS_RESULT_V1", request.request_digest, "1.13.0", METHOD,
        "dimensionless", LAYOUT, "SUPPORTED", length(request.times), request.points,
        result.coarse_points, 2*result.coarse_points, result.coarse_steps,
        result.fine_steps, result.coarse_drift, result.fine_drift, result.rms,
        result.maximum_difference, request.times[end], measured.time, request.times[1],
        measured.bytes,
    )
    for value in fields
        println(stdout, value)
    end
    println(stdout)
    # Julia's native column-major array order MUST NOT cross this protocol.
    # Explicit time-outer/x-inner loop emits little-endian C-order Float64.
    for row in axes(result.fine, 1), column in axes(result.fine, 2)
        write(stdout, htol(reinterpret(UInt64, result.fine[row, column])))
    end
    flush(stdout)
    return 0
end

exit(main())
